"""
Оркестратор процесса backup/restore баз данных
Управляет жизненным циклом отката БД после тестов
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from backend.config import get_restore_config
from backend.database.query_analyzer import QueryAnalyzer
from backend.database.backup_strategies import BackupInfo, SizeEstimate, SqlBackupStrategy
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
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_restore_config()
        self._analyzer = QueryAnalyzer()
        self._verifier = StateVerifier(self.config)
        
        # Выбираем стратегию бэкапа
        strategy_type = self.config.get("default_strategy", "sql")
        if strategy_type == "sql":
            self._strategy = SqlBackupStrategy(self.config)
        else:
            # В будущем: NativeDumpStrategy с fallback
            self._strategy = SqlBackupStrategy(self.config)
        
        # Блокировки для каждой СУБД (для параллельных тестов)
        self._locks: Dict[str, asyncio.Lock] = {
            "mysql": asyncio.Lock(),
            "postgresql": asyncio.Lock()
        }
        
        # Хранилище активных бэкапов (для ручного восстановления)
        self._active_backups: Dict[str, BackupInfo] = {}
    
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
        async with engine.connect() as conn:
            if dbms_type == 'postgresql':
                sql = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """
            else:
                sql = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    AND table_type = 'BASE TABLE'
                """
            
            result = await conn.execute(text(sql))
            return {row[0] for row in result}
    
    async def _get_row_count(self, engine: AsyncEngine, table: str, dbms_type: str) -> int:
        """Получить количество строк в таблице"""
        async with engine.connect() as conn:
            if dbms_type == 'postgresql':
                sql = f'SELECT COUNT(*) FROM "{table}"'
            else:
                sql = f'SELECT COUNT(*) FROM `{table}`'
            
            result = await conn.execute(text(sql))
            return result.scalar()
    
    def _get_lock(self, dbms_type: str) -> asyncio.Lock:
        """Получить блокировку для СУБД"""
        return self._locks.get(dbms_type, asyncio.Lock())
    
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
        # Проверяем, нужен ли backup
        if not self.needs_restore(queries):
            return PrepareResult(
                needs_backup=False,
                affected_tables=set(),
                size_estimate=None
            )
        
        # Получаем затронутые таблицы (для информации - какие таблицы были затронуты write-операциями)
        affected_tables = self.get_affected_tables(queries)
        
        if not affected_tables:
            return PrepareResult(
                needs_backup=False,
                affected_tables=set(),
                size_estimate=None
            )
        
        # Получаем ВСЕ таблицы базы для полного backup
        all_tables = await self._get_all_tables(engine, dbms_type)
        
        warnings = []
        
        # Проверяем остаточные backup-таблицы от предыдущих падений
        prefix = self.config.get("backup_table_prefix", "_loadtest_backup_")
        existing_backups = [t for t in all_tables if t.startswith(prefix)]
        if existing_backups:
            warnings.append(
                f"Found existing backup tables from previous test: {existing_backups}. "
                f"They will be replaced."
            )
        
        # Оцениваем размер для всех таблиц
        size_estimate = await self._strategy.estimate_size(engine, all_tables)
        
        # Проверяем пороги
        if size_estimate.total_rows > self.config.get("large_table_confirm_threshold", 10_000_000):
            warnings.append(
                f"Very large backup: {size_estimate.total_rows:,} rows total. "
                f"Consider using native dump strategy when excluding large tables."
            )
        elif size_estimate.warnings:
            warnings.extend(size_estimate.warnings)
        
        # Создаём backup для ВСЕХ таблиц
        backup_info = await self._strategy.create_backup(engine, all_tables)
        
        # Сохраняем фингерпринт до теста для всех таблиц
        pre_fingerprint = await self._verifier.capture_fingerprint(engine, all_tables)
        
        # Сохраняем информацию о бэкапе
        backup_key = f"{dbms_type}:{backup_info.backup_id}"
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
            return RestoreResult(
                success=True,
                duration_ms=0,
                verified=True
            )
        
        start_time = time.time()
        errors: List[str] = []
        
        # Блокируем СУБД на время restore
        async with self._get_lock(dbms_type):
            try:
                # Выполняем restore
                await self._strategy.restore_backup(engine, prepare_result.backup_info)
                
                # Проверяем, нужна ли верификация
                verified = True
                verify_result = None
                
                if self.config.get("verify_after_restore", True):
                    post_fingerprint = await self._verifier.capture_fingerprint(
                        engine, prepare_result.affected_tables
                    )
                    verify_result = await self._verifier.verify(
                        prepare_result.pre_test_fingerprint, post_fingerprint
                    )
                    verified = verify_result.success
                    if not verified:
                        errors.extend(verify_result.errors)
                
                # Очищаем backup после автоматического restore
                await self._strategy.cleanup(engine, prepare_result.backup_info)
                
                # Удаляем из активных бэкапов
                backup_key = f"{dbms_type}:{prepare_result.backup_info.backup_id}"
                self._active_backups.pop(backup_key, None)
                
                duration_ms = (time.time() - start_time) * 1000
                
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
                
                return RestoreResult(
                    success=False,
                    duration_ms=duration_ms,
                    verified=False,
                    errors=errors
                )
    
    async def manual_restore(self, engine: AsyncEngine, dbms_type: str, 
                            backup_id: str) -> RestoreResult:
        """
        Ручное восстановление из сохранённого бэкапа
        
        Args:
            engine: SQLAlchemy async engine
            dbms_type: Тип СУБД
            backup_id: ID бэкапа
            
        Returns:
            RestoreResult с результатами восстановления
        """
        backup_key = f"{dbms_type}:{backup_id}"
        
        if backup_key not in self._active_backups:
            return RestoreResult(
                success=False,
                duration_ms=0,
                verified=False,
                errors=[f"Backup {backup_id} not found for {dbms_type}"]
            )
        
        start_time = time.time()
        errors: List[str] = []
        
        backup_info = self._active_backups[backup_key]
        
        # Создаём фингерпринт текущего состояния
        pre_fingerprint = await self._verifier.capture_fingerprint(engine, backup_info.tables)
        
        try:
            # Выполняем restore
            await self._strategy.restore_backup(engine, backup_info)
            
            # Верификация
            verified = True
            verify_result = None
            if self.config.get("verify_after_restore", True):
                post_fingerprint = await self._verifier.capture_fingerprint(
                    engine, backup_info.tables
                )
                verify_result = await self._verifier.verify(pre_fingerprint, post_fingerprint)
                verified = verify_result.success
                if not verified:
                    errors.extend(verify_result.errors)
            
            # Очищаем backup после restore
            await self._strategy.cleanup(engine, backup_info)
            
            # Удаляем из активных бэкапов
            self._active_backups.pop(backup_key, None)
            
            duration_ms = (time.time() - start_time) * 1000
            
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
            
            return RestoreResult(
                success=False,
                duration_ms=duration_ms,
                verified=False,
                errors=errors
            )
    
    async def get_database_state(self, engine: AsyncEngine, dbms_type: str) -> Dict:
        """
        Получить текущее состояние БД
        
        Returns:
            Словарь с информацией о состоянии
        """
        prefix = self.config.get("backup_table_prefix", "_loadtest_backup_")
        
        async with engine.connect() as conn:
            # Получаем список таблиц (только BASE TABLE, исключая views)
            if dbms_type == 'postgresql':
                sql = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """
            else:  # mysql
                sql = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    AND table_type = 'BASE TABLE'
                """
            
            result = await conn.execute(text(sql))
            all_tables = [row[0] for row in result]
            
            # Проверяем backup-таблицы
            backup_tables = [t for t in all_tables if t.startswith(prefix)]
            original_tables = {t[len(prefix):] for t in backup_tables}
            
            # Собираем информацию о каждой таблице
            tables_info = {}
            for table in all_tables:
                row_count = await self._get_row_count(engine, table, dbms_type)
                tables_info[table] = {
                    "row_count": row_count,
                    "has_backup": table in original_tables
                }
            
            # Определяем статус
            if backup_tables:
                status = "backup_exists"
            else:
                status = "clean"
            
            return {
                "dbms_type": dbms_type,
                "tables": tables_info,
                "has_pending_backups": len(backup_tables) > 0,
                "backup_tables": backup_tables,
                "status": status
            }
