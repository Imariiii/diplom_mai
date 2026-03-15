"""
Backup strategies package for database state management
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Set, Optional, Any
from sqlalchemy import Engine


@dataclass
class BackupInfo:
    """Информация о созданном бэкапе"""
    backup_id: str
    dbms_type: str
    tables: Set[str]
    backup_tables: Set[str]
    row_counts: Dict[str, int]
    sequences: Optional[Dict[str, Dict]] = None  # Для PostgreSQL
    auto_increments: Optional[Dict[str, int]] = None  # Для MySQL
    created_at: datetime = None
    file_path: Optional[str] = None  # Для native стратегии
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class SizeEstimate:
    """Оценка размера бэкапа"""
    tables: Dict[str, Dict[str, Any]]  # {table: {rows, size_bytes}}
    total_rows: int
    total_size_bytes: int
    estimated_backup_time_sec: float
    warnings: list = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BackupStrategy(ABC):
    """Абстрактный базовый класс для стратегий бэкапа"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    @abstractmethod
    async def create_backup(self, engine: Engine, tables: Set[str]) -> BackupInfo:
        """
        Создать бэкап указанных таблиц
        
        Args:
            engine: SQLAlchemy engine
            tables: Множество имён таблиц для бэкапа
            
        Returns:
            BackupInfo с информацией о созданном бэкапе
        """
        pass
    
    @abstractmethod
    async def restore_backup(self, engine: Engine, backup_info: BackupInfo) -> None:
        """
        Восстановить данные из бэкапа
        
        Args:
            engine: SQLAlchemy engine
            backup_info: Информация о бэкапе (получена из create_backup)
        """
        pass
    
    @abstractmethod
    async def cleanup(self, engine: Engine, backup_info: BackupInfo) -> None:
        """
        Удалить временные объекты бэкапа
        
        Args:
            engine: SQLAlchemy engine
            backup_info: Информация о бэкапе
        """
        pass
    
    @abstractmethod
    async def estimate_size(self, engine: Engine, tables: Set[str]) -> SizeEstimate:
        """
        Оценить размер бэкапа
        
        Args:
            engine: SQLAlchemy engine
            tables: Множество имён таблиц
            
        Returns:
            SizeEstimate с оценкой размера и времени
        """
        pass
    
    def is_available(self) -> bool:
        """
        Проверить, доступна ли эта стратегия в текущем окружении
        
        Returns:
            True если стратегию можно использовать
        """
        return True
    
    def get_backup_table_name(self, table: str) -> str:
        """Получить имя backup-таблицы для указанной таблицы"""
        prefix = self.config.get("backup_table_prefix", "_loadtest_backup_")
        return f"{prefix}{table}"


# Экспортируем конкретные стратегии
try:
    from backend.database.backup_strategies.sql_strategy import SqlBackupStrategy
    __all__ = ['BackupStrategy', 'BackupInfo', 'SizeEstimate', 'SqlBackupStrategy']
except ImportError:
    __all__ = ['BackupStrategy', 'BackupInfo', 'SizeEstimate']

# Опционально: NativeDumpStrategy (требует pg_dump/mysqldump)
try:
    from backend.database.backup_strategies.native_strategy import NativeDumpStrategy
    __all__.append('NativeDumpStrategy')
except ImportError:
    pass
