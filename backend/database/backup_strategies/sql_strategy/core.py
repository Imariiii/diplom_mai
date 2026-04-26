"""
Основной класс SQL Backup Strategy
"""
from typing import Optional, Set
from sqlalchemy.ext.asyncio import AsyncEngine

from .. import BackupStrategy, BackupInfo, SizeEstimate
from backend.core.config import RestoreRuntimeConfig
from . import backup as backup_module
from . import restore as restore_module


class SqlBackupStrategy(BackupStrategy):
    """
    SQL-based стратегия бэкапа
    
    Создаёт копии таблиц через CREATE TABLE ... AS SELECT *
    Поддерживает PostgreSQL и MySQL
    """
    
    def __init__(self, config: Optional[RestoreRuntimeConfig] = None):
        super().__init__(config)
        self._locks = {}  # Блокировки для каждой БД
    
    async def create_backup(self, engine: AsyncEngine, tables: Set[str]) -> BackupInfo:
        """Создать бэкап таблиц через CREATE TABLE AS SELECT"""
        return await backup_module.create_backup_logic(
            engine=engine,
            tables=tables,
            get_backup_table_name_func=self.get_backup_table_name,
            config=self.config
        )
    
    async def restore_backup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Восстановить базу данных из бэкапа"""
        await restore_module.restore_backup_logic(
            engine=engine,
            backup_info=backup_info,
            get_backup_table_name_func=self.get_backup_table_name
        )
    
    async def cleanup(self, engine: AsyncEngine, backup_info: BackupInfo) -> None:
        """Удалить backup-таблицы"""
        await backup_module.cleanup_backup(
            engine=engine,
            tables=backup_info.tables,
            get_backup_table_name_func=self.get_backup_table_name
        )
    
    async def estimate_size(self, engine: AsyncEngine, tables: Set[str]) -> SizeEstimate:
        """Оценить размер бэкапа"""
        return await backup_module.estimate_size_logic(
            engine=engine,
            tables=tables,
            config=self.config
        )