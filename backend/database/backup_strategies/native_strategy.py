"""
Native dump strategy for database backup/restore using pg_dump/mysqldump
Optional fallback strategy when SQL-based strategy is not suitable for large databases
"""
import asyncio
import os
import shutil
import uuid
from typing import Dict, Set, Optional
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from . import BackupStrategy, BackupInfo, SizeEstimate


class NativeDumpStrategy(BackupStrategy):
    """
    Native dump strategy using pg_dump/mysqldump utilities
    
    Suitable for large databases where SQL-based backup might be slow.
    Requires pg_dump/pg_restore or mysqldump/mysql utilities to be installed.
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.snapshots_dir = config.get("snapshots_dir", "./snapshots") if config else "./snapshots"
        os.makedirs(self.snapshots_dir, exist_ok=True)
    
    def is_available(self) -> bool:
        """Check if native utilities are available"""
        return bool(shutil.which("pg_dump") or shutil.which("mysqldump"))
    
    def _get_connection_params(self, engine: AsyncEngine) -> Dict:
        """Extract connection parameters from SQLAlchemy async engine"""
        url = engine.url
        return {
            "host": url.host or "localhost",
            "port": url.port or (5432 if engine.sync_engine.dialect.name == "postgresql" else 3306),
            "user": url.username or "postgres",
            "password": url.password or "",
            "database": url.database or "postgres"
        }
    
    async def create_backup(self, engine: AsyncEngine, tables: Set[str]) -> BackupInfo:
        """Create backup using native dump utilities"""
        dbms_type = engine.sync_engine.dialect.name
        backup_id = str(uuid.uuid4())[:8]
        
        conn_params = self._get_connection_params(engine)
        
        if dbms_type == "postgresql":
            file_path = await self._create_postgres_backup(backup_id, conn_params, tables)
        elif dbms_type == "mysql":
            file_path = await self._create_mysql_backup(backup_id, conn_params, tables)
        else:
            raise ValueError(f"Unsupported DBMS type: {dbms_type}")
        
        # Get row counts for metadata
        row_counts = {}
        async with engine.connect() as conn:
            for table in tables:
                if dbms_type == "postgresql":
                    sql = f'SELECT COUNT(*) FROM "{table}"'
                else:
                    sql = f'SELECT COUNT(*) FROM `{table}`'
                result = await conn.execute(text(sql))
                row_counts[table] = result.scalar()
        
        return BackupInfo(
            backup_id=backup_id,
            dbms_type=dbms_type,
            tables=tables,
            backup_tables=set(),
            row_counts=row_counts,
            file_path=file_path
        )
    
    async def _create_postgres_backup(self, backup_id: str, conn_params: Dict, tables: Set[str]) -> str:
        """Create PostgreSQL backup using pg_dump"""
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
            raise RuntimeError(f"pg_dump failed: {stderr.decode()}")
        
        return file_path
    
    async def _create_mysql_backup(self, backup_id: str, conn_params: Dict, tables: Set[str]) -> str:
        """Create MySQL backup using mysqldump"""
        file_path = os.path.join(self.snapshots_dir, f"{backup_id}.sql")
        
        cmd = [
            "mysqldump",
            "-h", conn_params["host"],
            "-P", str(conn_params["port"]),
            "-u", conn_params["user"]
        ]
        
        if conn_params["password"]:
            cmd.extend(["-p" + conn_params["password"]])
        
        cmd.extend([
            "--single-transaction",
            "--routines",
            "--triggers",
            conn_params["database"]
        ] + list(tables))
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"mysqldump failed: {stderr.decode()}")
        
        with open(file_path, 'w') as f:
            f.write(stdout.decode())
        
        return file_path
    
    async def restore_backup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Restore database from native dump"""
        dbms_type = engine.sync_engine.dialect.name
        conn_params = self._get_connection_params(engine)
        
        if not backup_info.file_path or not os.path.exists(backup_info.file_path):
            raise ValueError(f"Backup file not found: {backup_info.file_path}")
        
        if dbms_type == "postgresql":
            await self._restore_postgres_backup(conn_params, backup_info.file_path)
        elif dbms_type == "mysql":
            await self._restore_mysql_backup(conn_params, backup_info.file_path)
    
    async def _restore_postgres_backup(self, conn_params: Dict, file_path: str) -> None:
        """Restore PostgreSQL database using pg_restore"""
        cmd = [
            "pg_restore",
            "-h", conn_params["host"],
            "-p", str(conn_params["port"]),
            "-U", conn_params["user"],
            "-d", conn_params["database"],
            "--clean",
            "--if-exists",
            "--no-owner",
            file_path
        ]
        
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
        
        if proc.returncode not in [0, 1]:
            raise RuntimeError(f"pg_restore failed: {stderr.decode()}")
    
    async def _restore_mysql_backup(self, conn_params: Dict, file_path: str) -> None:
        """Restore MySQL database using mysql client"""
        cmd = [
            "mysql",
            "-h", conn_params["host"],
            "-P", str(conn_params["port"]),
            "-u", conn_params["user"]
        ]
        
        if conn_params["password"]:
            cmd.extend(["-p" + conn_params["password"]])
        
        cmd.append(conn_params["database"])
        
        with open(file_path, 'r') as f:
            sql_content = f.read()
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate(input=sql_content.encode())
        
        if proc.returncode != 0:
            raise RuntimeError(f"mysql restore failed: {stderr.decode()}")
    
    async def cleanup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Remove backup file"""
        if backup_info.file_path and os.path.exists(backup_info.file_path):
            os.remove(backup_info.file_path)
    
    async def estimate_size(self, engine: AsyncEngine, tables: Set[str]) -> SizeEstimate:
        """Estimate backup size and time using native utilities"""
        dbms_type = engine.sync_engine.dialect.name
        
        table_info = {}
        total_rows = 0
        total_size = 0
        warnings = []
        
        async with engine.connect() as conn:
            for table in tables:
                if dbms_type == "postgresql":
                    row_sql = f'SELECT COUNT(*) FROM "{table}"'
                else:
                    row_sql = f'SELECT COUNT(*) FROM `{table}`'
                result = await conn.execute(text(row_sql))
                row_count = result.scalar()
                
                if dbms_type == "postgresql":
                    size_sql = f"SELECT pg_total_relation_size('\"{table}\"')"
                    size_result = await conn.execute(text(size_sql))
                else:
                    size_sql = text(
                        "SELECT DATA_LENGTH + INDEX_LENGTH FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
                    )
                    size_result = await conn.execute(size_sql, {"table": table})
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
