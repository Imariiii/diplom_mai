"""
Оркестратор процесса backup/restore баз данных
Управляет жизненным циклом отката БД после тестов
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from backend.core.config import RestoreRuntimeConfig, settings
from backend.database.query_analyzer import QueryAnalyzer
from backend.database.backup_strategies import BackupInfo, BackupStrategy, SizeEstimate, SqlBackupStrategy
from backend.database.dialects import get_dialect
from backend.database.sql_utils import get_row_count
from backend.database.state_verifier import StateVerifier, StateFingerprint, VerifyResult


@dataclass
class PrepareResult:
    """Результат подготовки к тесту"""
    needs_backup: bool
    affected_tables: Set[str]
    size_estimate: SizeEstimate
    backup_info: Optional[BackupInfo] = None
    pre_test_fingerprint: Optional[StateFingerprint] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class RestoreResult:
    """Результат восстановления после теста"""
    success: bool
    duration_ms: float
    verified: bool
    verify_result: Optional[VerifyResult] = None
    errors: List[str] = field(default_factory=list)


class DatabaseStateManager:
    """
    Оркестратор управления состояем баз данных
    
    Управляет процессом:
    1. Анализ запросов (нужен ли backup?)
    2. Создание backup
    3. Выполнение теста
    4. Восстановление данных
    5. Верификация
    6. Очистка
    """
    
    def __init__(self, config: Optional[RestoreRuntimeConfig] = None):
        self.config = config or RestoreRuntimeConfig.from_settings(settings)
        self._analyzer = QueryAnalyzer()
        self._verifier = StateVerifier(self.config)
        self._strategy = self._create_strategy()
        
        # Блокировки для каждой СУБД (для параллельных тестов)
        self._locks: Dict[str, asyncio.Lock] = {}
        
        # Хранилище активных бэкапов (для ручного восстановления)
        self._active_backups: Dict[str, BackupInfo] = {}

    def _build_strategy(self, strategy_name: str) -> BackupStrategy:
        """Построить стратегию по имени."""
        if strategy_name == "native":
            from backend.database.backup_strategies.native_strategy import NativeDumpStrategy
            strategy = NativeDumpStrategy(self.config)
            if not strategy.is_available():
                print("[BACKUP] Стратегия: native — утилиты (pg_dump/mysqldump/mariadb-dump) не найдены в PATH, откат на SQL-стратегию")
                return SqlBackupStrategy(self.config)
            return strategy
        return SqlBackupStrategy(self.config)

    def _create_strategy(self) -> BackupStrategy:
        """Создать стратегию бэкапа по текущей конфигурации."""
        strategy_name = self.config.default_strategy
        print(f"[BACKUP] Конфигурация: запрошена стратегия={strategy_name!r}")
        strategy = self._build_strategy(strategy_name)
        strategy_label = "Native (pg_dump / mysqldump / mariadb-dump)" if type(strategy).__name__ != "SqlBackupStrategy" else "SQL (CREATE TABLE AS SELECT)"
        print(f"[BACKUP] Стратегия: {strategy_label}")
        return strategy

    def _get_strategy_for_backup(self, backup_info: BackupInfo) -> BackupStrategy:
        """Получить стратегию, которой был создан конкретный бэкап."""
        strategy_name = backup_info.strategy_name or ("native" if backup_info.file_path else "sql")
        strategy = self._build_strategy(strategy_name)
        print(
            f"[BACKUP] [{backup_info.dbms_type}] Для backup_id={backup_info.backup_id} "
            f"используется стратегия восстановления={type(strategy).__name__} "
            f"(создано через {strategy_name})"
        )
        return strategy
    
    def needs_restore(self, queries: List[str]) -> bool:
        """
        Определить, нужен ли откат для данных запросов
        
        Args:
            queries: Список SQL запросов
            
        Returns:
            True если есть write-операции
        """
        return self._analyzer.has_write_operations(queries)
    
    def get_affected_tables(self, queries: List[str]) -> Set[str]:
        """
        Получить список затронутых таблиц
        
        Args:
            queries: Список SQL запросов
            
        Returns:
            Множество имён таблиц
        """
        return self._analyzer.extract_affected_tables(queries)
    
    async def _get_all_tables(self, engine: AsyncEngine, dbms_type: str) -> Set[str]:
        """Получить все таблицы базы данных"""
        dialect = get_dialect(dbms_type)
        async with engine.connect() as conn:
            result = await conn.execute(text(dialect.get_list_tables_sql()))
            return {row[0] for row in result}
    
    def _get_lock(self, dbms_type: str) -> asyncio.Lock:
        """Получить блокировку для СУБД"""
        return self._locks.setdefault(dbms_type, asyncio.Lock())
    
    def _refresh_config(self):
        """Перечитать конфигурацию из актуального состояния"""
        self.config = RestoreRuntimeConfig.from_settings(settings)
        self._verifier = StateVerifier(self.config)
        self._strategy = self._create_strategy()

    def refresh_config(self):
        """Публично перечитать конфигурацию и пересоздать активную стратегию."""
        self._refresh_config()

    @staticmethod
    def _make_backup_key(scope_key: str, backup_id: str) -> str:
        """Построить внутренний ключ хранения активного бэкапа."""
        return f"{scope_key}:{backup_id}"

    @staticmethod
    def _matches_scope(info: BackupInfo, storage_key: str, scope_key: Optional[str]) -> bool:
        """Проверить, относится ли бэкап к указанной области видимости."""
        if scope_key:
            if info.owner_key:
                return info.owner_key == scope_key
            return storage_key.startswith(f"{scope_key}:")
        return True

    async def prepare_for_test(self, engine: AsyncEngine, dbms_type: str, 
                             queries: List[str]) -> PrepareResult:
        """
        Подготовка к тесту: анализ, оценка, создание backup
        
        Args:
            engine: SQLAlchemy async engine
            dbms_type: Тип СУБД ("mysql" или "postgresql")
            queries: Список SQL запросов теста
            
        Returns:
            PrepareResult с результатами подготовки
        """
        self._refresh_config()
        
        strategy_label = type(self._strategy).__name__

        # Проверяем, нужен ли backup
        if not self.needs_restore(queries):
            print(f"[BACKUP] [{dbms_type}] Write-операций нет — бэкап не требуется")
            return PrepareResult(
                needs_backup=False,
                affected_tables=set(),
                size_estimate=None
            )
        
        # Получаем затронутые таблицы (для информации - какие таблицы были затронуты write-операциями)
        affected_tables = self.get_affected_tables(queries)
        
        if not affected_tables:
            print(f"[BACKUP] [{dbms_type}] Таблицы из write-запросов не определены — бэкап не требуется")
            return PrepareResult(
                needs_backup=False,
                affected_tables=set(),
                size_estimate=None
            )
        
        print(
            f"[BACKUP] [{dbms_type}] Старт подготовки | "
            f"стратегия={strategy_label} | "
            f"write-таблицы={sorted(affected_tables)}"
        )

        # Получаем ВСЕ таблицы базы для полного backup
        all_tables = await self._get_all_tables(engine, dbms_type)
        print(f"[BACKUP] [{dbms_type}] Таблиц в БД: {len(all_tables)}")
        
        warnings = []
        
        # Проверяем остаточные backup-таблицы от предыдущих падений
        prefix = self.config.backup_table_prefix
        existing_backups = [t for t in all_tables if t.startswith(prefix)]
        if existing_backups:
            print(f"[BACKUP] [{dbms_type}] ПРЕДУПРЕЖДЕНИЕ: найдены остатки предыдущего бэкапа: {existing_backups}")
            warnings.append(
                f"Found existing backup tables from previous test: {existing_backups}. "
                f"They will be replaced."
            )
        
        # Оцениваем размер для всех таблиц
        size_estimate = await self._strategy.estimate_size(engine, all_tables)
        print(
            f"[BACKUP] [{dbms_type}] Оценка размера: "
            f"{size_estimate.total_rows:,} строк, "
            f"~{size_estimate.total_size_bytes / 1024 / 1024:.1f} МБ, "
            f"~{size_estimate.estimated_backup_time_sec:.1f}с"
        )
        
        # Проверяем пороги
        if size_estimate.total_rows > self.config.large_table_confirm_threshold:
            msg = (
                f"Very large backup: {size_estimate.total_rows:,} rows total. "
                f"Consider using native dump strategy when excluding large tables."
            )
            print(f"[BACKUP] [{dbms_type}] ПРЕДУПРЕЖДЕНИЕ: {msg}")
            warnings.append(msg)
        elif size_estimate.warnings:
            for w in size_estimate.warnings:
                print(f"[BACKUP] [{dbms_type}] ПРЕДУПРЕЖДЕНИЕ: {w}")
            warnings.extend(size_estimate.warnings)
        
        # Создаём backup для ВСЕХ таблиц
        print(f"[BACKUP] [{dbms_type}] Создание бэкапа ({len(all_tables)} таблиц) через {strategy_label}...")
        backup_start = time.time()
        backup_info = await self._strategy.create_backup(engine, all_tables)
        backup_duration_ms = (time.time() - backup_start) * 1000
        
        total_rows_backed = sum(backup_info.row_counts.values())
        print(
            f"[BACKUP] [{dbms_type}] Бэкап создан | "
            f"id={backup_info.backup_id} | "
            f"таблиц={len(backup_info.tables)} | "
            f"строк={total_rows_backed:,} | "
            f"время={backup_duration_ms:.0f}мс"
        )
        if backup_info.file_path:
            print(f"[BACKUP] [{dbms_type}] Файл дампа: {backup_info.file_path}")
        
        # Сохраняем фингерпринт до теста для всех таблиц
        pre_fingerprint = await self._verifier.capture_fingerprint(engine, all_tables)
        
        # Сохраняем информацию о бэкапе
        backup_key = self._make_backup_key(dbms_type, backup_info.backup_id)
        self._active_backups[backup_key] = backup_info
        
        return PrepareResult(
            needs_backup=True,
            affected_tables=affected_tables,  # Для информации - какие таблицы были затронуты write-операциями
            size_estimate=size_estimate,
            backup_info=backup_info,
            pre_test_fingerprint=pre_fingerprint,
            warnings=warnings
        )
    
    async def restore_after_test(self, engine: AsyncEngine, dbms_type: str,
                                prepare_result: PrepareResult) -> RestoreResult:
        """
        Восстановление данных после теста
        
        Args:
            engine: SQLAlchemy async engine
            dbms_type: Тип СУБД
            prepare_result: Результат подготовки (от prepare_for_test)
            
        Returns:
            RestoreResult с результатами восстановления
        """
        if not prepare_result.needs_backup or not prepare_result.backup_info:
            print(f"[RESTORE] [{dbms_type}] Восстановление пропущено — бэкап не создавался")
            return RestoreResult(
                success=True,
                duration_ms=0,
                verified=True
            )
        
        backup_strategy = self._get_strategy_for_backup(prepare_result.backup_info)
        strategy_label = type(backup_strategy).__name__
        backup_id = prepare_result.backup_info.backup_id
        tables_count = len(prepare_result.backup_info.tables)
        total_rows = sum(prepare_result.backup_info.row_counts.values())

        print(
            f"[RESTORE] [{dbms_type}] Старт восстановления (авто) | "
            f"стратегия={strategy_label} | "
            f"backup_id={backup_id} | "
            f"таблиц={tables_count} | "
            f"строк={total_rows:,}"
        )

        start_time = time.time()
        errors: List[str] = []
        
        # Блокируем СУБД на время restore
        async with self._get_lock(dbms_type):
            try:
                # Выполняем restore
                await backup_strategy.restore_backup(engine, prepare_result.backup_info)
                
                # Проверяем, нужна ли верификация
                verified = True
                verify_result = None
                
                if self.config.verify_after_restore:
                    print(f"[RESTORE] [{dbms_type}] Верификация состояния...")
                    post_fingerprint = await self._verifier.capture_fingerprint(
                        engine, prepare_result.backup_info.tables
                    )
                    verify_result = await self._verifier.verify(
                        prepare_result.pre_test_fingerprint, post_fingerprint
                    )
                    verified = verify_result.success
                    if verified:
                        print(f"[RESTORE] [{dbms_type}] Верификация: OK")
                    else:
                        print(f"[RESTORE] [{dbms_type}] Верификация: ОШИБКИ — {verify_result.errors}")
                        errors.extend(verify_result.errors)
                else:
                    print(f"[RESTORE] [{dbms_type}] Верификация отключена в настройках")
                
                # Очищаем backup после автоматического restore
                await backup_strategy.cleanup(engine, prepare_result.backup_info)
                
                # Удаляем из активных бэкапов
                backup_key = self._make_backup_key(dbms_type, backup_id)
                self._active_backups.pop(backup_key, None)
                
                duration_ms = (time.time() - start_time) * 1000
                status = "успешно" if verified else "с ошибками верификации"
                print(
                    f"[RESTORE] [{dbms_type}] Восстановление завершено {status} | "
                    f"backup_id={backup_id} | "
                    f"время={duration_ms:.0f}мс"
                )
                
                return RestoreResult(
                    success=verified,
                    duration_ms=duration_ms,
                    verified=verified,
                    verify_result=verify_result,
                    errors=errors
                )
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                errors.append(str(e))
                print(
                    f"[RESTORE] [{dbms_type}] ОШИБКА восстановления | "
                    f"backup_id={backup_id} | "
                    f"время={duration_ms:.0f}мс | "
                    f"ошибка: {e}"
                )
                
                return RestoreResult(
                    success=False,
                    duration_ms=duration_ms,
                    verified=False,
                    errors=errors
                )
    
    def get_active_backup_id(self, dbms_type: str, scope_key: Optional[str] = None) -> Optional[str]:
        """
        Получить ID последнего активного бэкапа для данного типа СУБД
        
        Args:
            dbms_type: Тип СУБД
            
        Returns:
            backup_id или None
        """
        for key, info in self._active_backups.items():
            if info.dbms_type != dbms_type:
                continue
            if self._matches_scope(info, key, scope_key):
                return info.backup_id
        return None

    async def manual_restore(self, engine: AsyncEngine, dbms_type: str, 
                            backup_id: Optional[str] = None,
                            scope_key: Optional[str] = None) -> RestoreResult:
        """
        Ручное восстановление из сохранённого бэкапа
        
        Args:
            engine: SQLAlchemy async engine
            dbms_type: Тип СУБД
            backup_id: ID бэкапа (если None — восстановит последний активный)
            
        Returns:
            RestoreResult с результатами восстановления
        """
        if not backup_id:
            backup_id = self.get_active_backup_id(dbms_type, scope_key=scope_key)
        
        if not backup_id:
            print(f"[RESTORE] [{dbms_type}] Ручное восстановление: нет активных бэкапов")
            return RestoreResult(
                success=False,
                duration_ms=0,
                verified=False,
                errors=[f"Нет активных бэкапов для {dbms_type}"]
            )
        
        backup_key = None
        for key, info in self._active_backups.items():
            if info.dbms_type != dbms_type or info.backup_id != backup_id:
                continue
            if self._matches_scope(info, key, scope_key):
                backup_key = key
                break

        if backup_key is None:
            print(f"[RESTORE] [{dbms_type}] Ручное восстановление: бэкап {backup_id} не найден в активных")
            return RestoreResult(
                success=False,
                duration_ms=0,
                verified=False,
                errors=[f"Backup {backup_id} not found for {dbms_type}"]
            )
        
        backup_info = self._active_backups[backup_key]
        backup_strategy = self._get_strategy_for_backup(backup_info)
        strategy_label = type(backup_strategy).__name__
        tables_count = len(backup_info.tables)
        total_rows = sum(backup_info.row_counts.values())

        print(
            f"[RESTORE] [{dbms_type}] Старт восстановления (ручное) | "
            f"стратегия={strategy_label} | "
            f"backup_id={backup_id} | "
            f"таблиц={tables_count} | "
            f"строк={total_rows:,}"
        )
        if backup_info.file_path:
            print(f"[RESTORE] [{dbms_type}] Файл дампа: {backup_info.file_path}")

        start_time = time.time()
        errors: List[str] = []
        
        # Создаём фингерпринт текущего состояния
        pre_fingerprint = await self._verifier.capture_fingerprint(engine, backup_info.tables)
        
        try:
            # Выполняем restore
            await backup_strategy.restore_backup(engine, backup_info)
            
            # Верификация
            verified = True
            verify_result = None
            if self.config.verify_after_restore:
                print(f"[RESTORE] [{dbms_type}] Верификация состояния...")
                post_fingerprint = await self._verifier.capture_fingerprint(
                    engine, backup_info.tables
                )
                verify_result = await self._verifier.verify(pre_fingerprint, post_fingerprint)
                verified = verify_result.success
                if verified:
                    print(f"[RESTORE] [{dbms_type}] Верификация: OK")
                else:
                    print(f"[RESTORE] [{dbms_type}] Верификация: ОШИБКИ — {verify_result.errors}")
                    errors.extend(verify_result.errors)
            else:
                print(f"[RESTORE] [{dbms_type}] Верификация отключена в настройках")
            
            # Очищаем backup после restore
            await backup_strategy.cleanup(engine, backup_info)
            
            # Удаляем из активных бэкапов
            self._active_backups.pop(backup_key, None)
            
            duration_ms = (time.time() - start_time) * 1000
            status = "успешно" if verified else "с ошибками верификации"
            print(
                f"[RESTORE] [{dbms_type}] Восстановление завершено {status} | "
                f"backup_id={backup_id} | "
                f"время={duration_ms:.0f}мс"
            )
            
            return RestoreResult(
                success=verified,
                duration_ms=duration_ms,
                verified=verified,
                verify_result=verify_result,
                errors=errors
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            errors.append(str(e))
            print(
                f"[RESTORE] [{dbms_type}] ОШИБКА восстановления | "
                f"backup_id={backup_id} | "
                f"время={duration_ms:.0f}мс | "
                f"ошибка: {e}"
            )
            
            return RestoreResult(
                success=False,
                duration_ms=duration_ms,
                verified=False,
                errors=errors
            )
    
    async def cleanup_all_backups(self, engine: AsyncEngine, dbms_type: str, scope_key: Optional[str] = None) -> List[str]:
        """
        Найти и удалить все backup-таблицы из БД, а также файлы native-дампов.
        
        Args:
            engine: SQLAlchemy async engine
            dbms_type: Тип СУБД
            
        Returns:
            Список удалённых backup-таблиц / файлов
        """
        import os

        deleted = []
        strategy_label = type(self._strategy).__name__
        print(f"[BACKUP] [{dbms_type}] Очистка бэкапов | стратегия={strategy_label}")

        # SQL-стратегия: удаляем backup-таблицы из БД
        prefix = self.config.backup_table_prefix
        all_tables = await self._get_all_tables(engine, dbms_type)
        backup_tables = [t for t in all_tables if t.startswith(prefix)]
        
        if backup_tables:
            print(f"[BACKUP] [{dbms_type}] Удаление {len(backup_tables)} backup-таблиц: {backup_tables}")
            dialect = get_dialect(dbms_type)
            async with engine.connect() as conn:
                for table in backup_tables:
                    try:
                        await conn.execute(text(dialect.get_drop_table_sql(table, cascade=True)))
                        deleted.append(table)
                        print(f"[BACKUP] [{dbms_type}] Удалена таблица: {table}")
                    except Exception as e:
                        print(f"[BACKUP] [{dbms_type}] ОШИБКА удаления таблицы {table}: {e}")
                await conn.commit()
        else:
            print(f"[BACKUP] [{dbms_type}] Backup-таблиц в БД не найдено")

        # Native-стратегия: удаляем файлы дампов из активных бэкапов
        keys_to_remove = [
            k for k, info in self._active_backups.items()
            if info.dbms_type == dbms_type and self._matches_scope(info, k, scope_key)
        ]
        for key in keys_to_remove:
            info = self._active_backups.pop(key, None)
            if info and info.file_path:
                try:
                    if os.path.exists(info.file_path):
                        os.remove(info.file_path)
                        deleted.append(info.file_path)
                        print(f"[BACKUP] [{dbms_type}] Удалён файл дампа: {info.file_path}")
                    else:
                        print(f"[BACKUP] [{dbms_type}] Файл дампа уже отсутствует: {info.file_path}")
                except Exception as e:
                    print(f"[BACKUP] [{dbms_type}] ОШИБКА удаления файла дампа {info.file_path}: {e}")

        print(f"[BACKUP] [{dbms_type}] Очистка завершена: удалено {len(deleted)} объектов")
        return deleted

    async def get_database_state(self, engine: AsyncEngine, dbms_type: str, scope_key: Optional[str] = None) -> Dict:
        """
        Получить текущее состояние БД
        
        Returns:
            Словарь с информацией о состоянии
        """
        prefix = self.config.backup_table_prefix
        dialect = get_dialect(dbms_type)
        
        async with engine.connect() as conn:
            # Получаем список таблиц (только BASE TABLE, исключая views)
            result = await conn.execute(text(dialect.get_list_tables_sql()))
            all_tables = [row[0] for row in result]
            
            # Проверяем backup-таблицы
            backup_tables = [t for t in all_tables if t.startswith(prefix)]
            original_tables = {t[len(prefix):] for t in backup_tables}
            
            # Собираем информацию о каждой таблице
            tables_info = {}
            for table in all_tables:
                row_count = await get_row_count(engine, table, dbms_type)
                tables_info[table] = {
                    "row_count": row_count,
                    "has_backup": table in original_tables
                }
            
            # Проверяем наличие active native-дампов для этого типа СУБД
            native_backups = [
                v for k, v in self._active_backups.items()
                if v.dbms_type == dbms_type and v.file_path and self._matches_scope(v, k, scope_key)
            ]
            has_native_backups = len(native_backups) > 0

            has_pending = len(backup_tables) > 0 or has_native_backups
            status = "backup_exists" if has_pending else "clean"
            pending_backup_strategy = "sql" if backup_tables else ("native" if has_native_backups else None)
            pending_backup_count = len(backup_tables) if backup_tables else len(native_backups)
            
            return {
                "dbms_type": dbms_type,
                "tables": tables_info,
                "has_pending_backups": has_pending,
                "backup_tables": backup_tables,
                "pending_backup_count": pending_backup_count,
                "pending_backup_strategy": pending_backup_strategy,
                "status": status
            }
