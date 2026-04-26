"""
Native dump стратегия backup/restore через pg_dump/mysqldump (mariadb-dump).

Подходит для больших баз данных (>10M строк), где SQL-стратегия (CREATE TABLE AS SELECT)
становится неэффективной. Интегрирована в DatabaseStateManager через конфиг
default_strategy="native".

Поддерживает PostgreSQL, MySQL и MariaDB.
"""
import asyncio
import os
import re
import shutil
import uuid
from typing import Dict, Set, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from . import BackupStrategy, BackupInfo, SizeEstimate
from backend.core.config import RestoreRuntimeConfig
from backend.core.docker import resolve_host
from backend.database.dialects import get_dialect
from backend.database.sql_utils import resolve_dbms_type


class NativeDumpStrategy(BackupStrategy):
    """
    Native dump стратегия через pg_dump/pg_restore и mysqldump/mysql (mariadb-dump/mariadb).
    
    Требует наличия соответствующих утилит в PATH.
    """
    
    def __init__(self, config: Optional[RestoreRuntimeConfig] = None):
        super().__init__(config)
        self.snapshots_dir = self.config.snapshots_dir
        os.makedirs(self.snapshots_dir, exist_ok=True)
    
    def is_available(self) -> bool:
        """Проверить, доступны ли native-утилиты в окружении"""
        has_pg = bool(shutil.which("pg_dump"))
        has_mysql = bool(
            shutil.which("mysqldump") or shutil.which("mariadb-dump")
        )
        return has_pg or has_mysql

    @staticmethod
    def _resolve_mysql_binaries(dbms_type: str) -> Tuple[str, str]:
        """Определить бинарники dump/restore для MySQL-семейства (MySQL и MariaDB)."""
        if dbms_type == "mariadb":
            dump_cmd = shutil.which("mariadb-dump") or shutil.which("mysqldump")
            restore_cmd = shutil.which("mariadb") or shutil.which("mysql")
        else:
            dump_cmd = shutil.which("mysqldump") or shutil.which("mariadb-dump")
            restore_cmd = shutil.which("mysql") or shutil.which("mariadb")
        if not dump_cmd or not restore_cmd:
            raise RuntimeError(
                f"Не найдены утилиты дампа/восстановления для {dbms_type}. "
                f"Установите mysqldump/mysql или mariadb-dump/mariadb."
            )
        return dump_cmd, restore_cmd

    @staticmethod
    def _get_mysql_client_ssl_args() -> list[str]:
        """
        Отключить SSL для mysql/mysqldump/mariadb-dump/mariadb.

        Основные SQLAlchemy-подключения проекта работают без явной SSL-конфигурации,
        а CLI-клиенты в контейнере могут пытаться включить TLS автоматически, что
        приводит к Certificate verification failure при локальных/тестовых подключениях.
        """
        return ["--skip-ssl"]

    @staticmethod
    def _sanitize_mysql_dump_definers(sql_content: bytes) -> Tuple[bytes, int]:
        """
        Удалить DEFINER из MySQL/MariaDB дампа перед восстановлением.

        Дампы триггеров могут содержать DEFINER исходного сервера, например
        root@localhost. При восстановлении обычным пользователем MariaDB требует
        SET USER и прерывает импорт, хотя данные до этой строки уже применены.
        """
        versioned_definer_pattern = re.compile(
            rb"/\*![0-9]{5}\s+DEFINER=`[^`]+`@`[^`]+`\s*\*/\s*"
        )
        plain_definer_pattern = re.compile(
            rb"\bDEFINER\s*=\s*(?:"
            rb"`[^`]+`@`[^`]+`|"
            rb"'[^']+'@'[^']+'|"
            rb'"[^"]+"@"[^"]+"|'
            rb"[^\s@]+@[^\s]+|"
            rb"CURRENT_USER(?:\(\))?"
            rb")\s+",
            re.IGNORECASE,
        )

        sanitized, versioned_count = versioned_definer_pattern.subn(b"", sql_content)
        sanitized, plain_count = plain_definer_pattern.subn(b"", sanitized)
        return sanitized, versioned_count + plain_count

    def _get_connection_params(self, engine: AsyncEngine) -> Dict:
        """Извлечь параметры подключения из SQLAlchemy async engine"""
        url = engine.url
        dbms_type = resolve_dbms_type(engine)
        dialect = get_dialect(dbms_type)
        return {
            "host": resolve_host(url.host or "localhost"),
            "port": url.port or dialect.default_port,
            "user": url.username or "postgres",
            "password": url.password or "",
            "database": url.database or "postgres"
        }
    
    async def create_backup(self, engine: AsyncEngine, tables: Set[str]) -> BackupInfo:
        """Создать бэкап через native-утилиты"""
        import time as _time
        dbms_type = resolve_dbms_type(engine)
        dialect = get_dialect(dbms_type)
        backup_id = str(uuid.uuid4())[:8]
        
        conn_params = self._get_connection_params(engine)
        print(
            f"[BACKUP:Native] [{dbms_type}] Старт дампа | "
            f"backup_id={backup_id} | "
            f"таблиц={len(tables)} | "
            f"база={conn_params['database']} | "
            f"хост={conn_params['host']}:{conn_params['port']}"
        )

        t0 = _time.time()
        if dialect.native_dump_family == "postgresql":
            file_path = await self._create_postgres_backup(backup_id, conn_params, tables)
        elif dialect.native_dump_family == "mysql":
            file_path = await self._create_mysql_backup(
                backup_id, conn_params, tables, dbms_type
            )
        else:
            raise ValueError(f"Unsupported DBMS type: {dbms_type}")
        
        dump_ms = (_time.time() - t0) * 1000
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024 if os.path.exists(file_path) else 0
        print(
            f"[BACKUP:Native] [{dbms_type}] Дамп создан | "
            f"файл={file_path} | "
            f"размер={file_size_mb:.1f}МБ | "
            f"время={dump_ms:.0f}мс"
        )

        row_counts = {}
        async with engine.connect() as conn:
            for table in tables:
                result = await conn.execute(text(dialect.get_row_count_sql(table)))
                row_counts[table] = result.scalar()
        
        total_rows = sum(row_counts.values())
        print(f"[BACKUP:Native] [{dbms_type}] Строк в дампе: {total_rows:,} (по {len(row_counts)} таблицам)")

        return BackupInfo(
            backup_id=backup_id,
            dbms_type=dbms_type,
            tables=tables,
            backup_tables=set(),
            row_counts=row_counts,
            strategy_name="native",
            file_path=file_path
        )
    
    async def _create_postgres_backup(
        self, backup_id: str, conn_params: Dict, tables: Set[str]
    ) -> str:
        """Бэкап PostgreSQL через pg_dump"""
        file_path = os.path.join(self.snapshots_dir, f"{backup_id}.dump")
        
        table_args = []
        for table in tables:
            table_args.extend(["-t", table])
        
        cmd = [
            "pg_dump",
            "-h", conn_params["host"],
            "-p", str(conn_params["port"]),
            "-U", conn_params["user"],
            "-d", conn_params["database"],
            "--format=custom",
            "--no-owner",
            "--no-privileges"
        ] + table_args + ["-f", file_path]
        
        print(f"[BACKUP:Native] [postgresql] Запуск pg_dump → {file_path}")
        env = os.environ.copy()
        if conn_params["password"]:
            env["PGPASSWORD"] = conn_params["password"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            print(f"[BACKUP:Native] [postgresql] ОШИБКА pg_dump (код {proc.returncode}): {stderr.decode()}")
            raise RuntimeError(f"pg_dump failed: {stderr.decode()}")
        
        return file_path
    
    async def _create_mysql_backup(
        self,
        backup_id: str,
        conn_params: Dict,
        tables: Set[str],
        dbms_type: str = "mysql",
    ) -> str:
        """Бэкап MySQL/MariaDB через mysqldump или mariadb-dump"""
        file_path = os.path.join(self.snapshots_dir, f"{backup_id}.sql")
        dump_cmd, _ = self._resolve_mysql_binaries(dbms_type)
        
        cmd = [
            dump_cmd,
            "-h", conn_params["host"],
            "-P", str(conn_params["port"]),
            "-u", conn_params["user"]
        ] + self._get_mysql_client_ssl_args()
        
        if conn_params["password"]:
            cmd.extend(["-p" + conn_params["password"]])
        
        cmd.extend([
            "--single-transaction",
            "--triggers",
            "--hex-blob",
            "--no-tablespaces",
            f"--result-file={file_path}",
            conn_params["database"]
        ] + list(tables))
        
        print(f"[BACKUP:Native] [{dbms_type}] Запуск {dump_cmd} → {file_path}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            stderr_text = stderr.decode(errors="replace")
            print(f"[BACKUP:Native] [{dbms_type}] ОШИБКА {dump_cmd} (код {proc.returncode}): {stderr_text}")
            raise RuntimeError(f"{dump_cmd} failed: {stderr_text}")
        
        return file_path
    
    async def restore_backup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Восстановить БД из native-дампа"""
        import time as _time
        dbms_type = backup_info.dbms_type or resolve_dbms_type(engine)
        dialect = get_dialect(dbms_type)
        conn_params = self._get_connection_params(engine)
        
        if not backup_info.file_path or not os.path.exists(backup_info.file_path):
            raise ValueError(f"Backup file not found: {backup_info.file_path}")
        
        file_size_mb = os.path.getsize(backup_info.file_path) / 1024 / 1024
        print(
            f"[RESTORE:Native] [{dbms_type}] Старт восстановления | "
            f"backup_id={backup_info.backup_id} | "
            f"файл={backup_info.file_path} | "
            f"размер={file_size_mb:.1f}МБ"
        )

        t0 = _time.time()
        if dialect.native_dump_family == "postgresql":
            await self._restore_postgres_backup(
                engine, conn_params, backup_info.file_path, backup_info.tables
            )
        elif dialect.native_dump_family == "mysql":
            await self._restore_mysql_backup(
                conn_params, backup_info.file_path, dbms_type
            )
        restore_ms = (_time.time() - t0) * 1000
        print(
            f"[RESTORE:Native] [{dbms_type}] Восстановление завершено | "
            f"backup_id={backup_info.backup_id} | "
            f"время={restore_ms:.0f}мс"
        )
    
    async def _truncate_postgres_tables(
        self,
        engine: AsyncEngine,
        tables: Set[str],
    ) -> None:
        """Очистить таблицы перед data-only восстановлением PostgreSQL."""
        if not tables:
            return

        dialect = get_dialect("postgresql")
        quoted_tables = ", ".join(
            dialect.quote_identifier(table) for table in sorted(tables)
        )
        sql = f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"

        async with engine.connect() as conn:
            await conn.execute(text(sql))
            await conn.commit()

        print(
            f"[RESTORE:Native] [postgresql] Таблицы очищены перед импортом: "
            f"{len(tables)}"
        )

    async def _restore_postgres_backup(
        self,
        engine: AsyncEngine,
        conn_params: Dict,
        file_path: str,
        tables: Set[str],
    ) -> None:
        """Восстановление PostgreSQL через pg_restore"""
        await self._truncate_postgres_tables(engine, tables)

        cmd = [
            "pg_restore",
            "-h", conn_params["host"],
            "-p", str(conn_params["port"]),
            "-U", conn_params["user"],
            "-d", conn_params["database"],
            "--data-only",
            "--disable-triggers",
            "--no-owner",
            file_path
        ]
        
        print(f"[RESTORE:Native] [postgresql] Запуск pg_restore ← {file_path}")
        env = os.environ.copy()
        if conn_params["password"]:
            env["PGPASSWORD"] = conn_params["password"]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            print(f"[RESTORE:Native] [postgresql] ОШИБКА pg_restore (код {proc.returncode}): {stderr.decode()}")
            raise RuntimeError(f"pg_restore failed: {stderr.decode()}")
        if stderr:
            stderr_text = stderr.decode().strip()
            if stderr_text:
                print(f"[RESTORE:Native] [postgresql] pg_restore предупреждения: {stderr_text[:200]}")
    
    async def _restore_mysql_backup(
        self,
        conn_params: Dict,
        file_path: str,
        dbms_type: str = "mysql",
    ) -> None:
        """Восстановление MySQL/MariaDB через mysql или mariadb"""
        _, restore_cmd = self._resolve_mysql_binaries(dbms_type)
        
        cmd = [
            restore_cmd,
            "-h", conn_params["host"],
            "-P", str(conn_params["port"]),
            "-u", conn_params["user"]
        ] + self._get_mysql_client_ssl_args()
        
        if conn_params["password"]:
            cmd.extend(["-p" + conn_params["password"]])
        
        cmd.append(conn_params["database"])
        
        print(f"[RESTORE:Native] [{dbms_type}] Запуск {restore_cmd} ← {file_path}")
        with open(file_path, 'rb') as f:
            sql_content = f.read()

        sql_content, removed_definers = self._sanitize_mysql_dump_definers(sql_content)
        if removed_definers:
            print(
                f"[RESTORE:Native] [{dbms_type}] "
                f"Удалены DEFINER из дампа: {removed_definers}"
            )
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate(input=sql_content)
        
        if proc.returncode != 0:
            stderr_text = stderr.decode(errors="replace")
            print(f"[RESTORE:Native] [{dbms_type}] ОШИБКА {restore_cmd} (код {proc.returncode}): {stderr_text}")
            raise RuntimeError(f"{restore_cmd} restore failed: {stderr_text}")
    
    async def cleanup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Удалить файл дампа"""
        if backup_info.file_path and os.path.exists(backup_info.file_path):
            os.remove(backup_info.file_path)
            print(
                f"[BACKUP:Native] [{backup_info.dbms_type}] "
                f"Файл дампа удалён: {backup_info.file_path}"
            )
    
    async def estimate_size(self, engine: AsyncEngine, tables: Set[str]) -> SizeEstimate:
        """Оценить размер бэкапа"""
        dbms_type = resolve_dbms_type(engine)
        dialect = get_dialect(dbms_type)
        
        table_info = {}
        total_rows = 0
        total_size = 0
        warnings = []
        
        async with engine.connect() as conn:
            for table in tables:
                result = await conn.execute(text(dialect.get_row_count_sql(table)))
                row_count = result.scalar()
                
                size_result = await conn.execute(text(dialect.get_table_size_sql(table)))
                size_bytes = size_result.scalar() or 0
                
                table_info[table] = {
                    "rows": row_count,
                    "size_bytes": size_bytes
                }
                total_rows += row_count
                total_size += size_bytes
                
                if row_count > 10_000_000:
                    warnings.append(f"Very large table {table} ({row_count:,} rows)")
                elif row_count > 1_000_000:
                    warnings.append(f"Large table {table} ({row_count:,} rows)")
        
        estimated_time = max(total_rows / 5000, 0.5)
        
        return SizeEstimate(
            tables=table_info,
            total_rows=total_rows,
            total_size_bytes=total_size,
            estimated_backup_time_sec=estimated_time,
            warnings=warnings
        )
