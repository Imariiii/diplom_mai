"""
Централизованная конфигурация системы отката баз данных

Использует Pydantic BaseSettings для управления конфигурацией через:
- Переменные окружения
- Файл .env
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Настройки подключения к базам данных"""

    # History database
    history_db_url: Optional[str] = Field(default=None, alias="HISTORY_DATABASE_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class RestoreSettings(BaseSettings):
    """Настройки восстановления баз данных"""
    
    # Стратегия по умолчанию: "sql" или "native"
    default_strategy: str = Field(default="sql")
    
    # Автоматически восстанавливать БД после write-тестов
    auto_restore: bool = Field(default=True)
    
    # Верифицировать состояние после восстановления
    verify_after_restore: bool = Field(default=True)
    
    # Порог предупреждения: если таблица больше N строк — предупредить
    large_table_warning_threshold: int = Field(default=1_000_000)
    
    # Порог запрета: если таблица больше N строк — требовать подтверждение
    large_table_confirm_threshold: int = Field(default=10_000_000)
    
    # Максимальное количество retry при неудачном restore
    max_restore_retries: int = Field(default=2)
    
    # Таймаут на операцию backup/restore (секунды)
    operation_timeout: int = Field(default=300)
    
    # Префикс для backup-таблиц в SQL-стратегии
    backup_table_prefix: str = Field(default="_loadtest_backup_")
    
    # Включить чексуммы при верификации (медленнее, но надёжнее)
    verify_checksums: bool = Field(default=False)
    
    # Максимальный размер таблицы для чексуммы (строк)
    checksum_max_rows: int = Field(default=100_000)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class PathSettings(BaseSettings):
    """Настройки путей"""
    
    # Директория для snapshots/дампов
    snapshots_dir: str = Field(default="./snapshots")
    
    # Директория для логов
    logs_dir: str = Field(default="./logs")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class APISettings(BaseSettings):
    """Настройки API"""
    
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class TestSettings(BaseSettings):
    """Настройки тестирования"""
    
    default_users: int = Field(default=10)
    default_spawn_rate: int = Field(default=2)
    default_duration: int = Field(default=60)
    default_queries: list = Field(default_factory=lambda: [
        "SELECT * FROM actor LIMIT 100",
        "SELECT * FROM film WHERE length > 120",
        "SELECT COUNT(*) FROM rental",
        "SELECT customer_id, COUNT(*) FROM rental GROUP BY customer_id"
    ])
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class Settings(BaseSettings):
    """
    Главный класс настроек приложения
    
    Объединяет все настройки в единый центр конфигурации.
    Использует Pydantic BaseSettings для загрузки из переменных окружения и .env файла.
    
    Пример использования:
        from backend.core.config import settings
        
        print(settings.history_db_url)
        print(settings.auto_restore)    # True
    """
    
    # Подгружаем вложенные настройки
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    restore: RestoreSettings = Field(default_factory=RestoreSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    api: APISettings = Field(default_factory=APISettings)
    test: TestSettings = Field(default_factory=TestSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        extra = "ignore"
    
    # Прокси- свойства для обратной совместимости
    
    @property
    def history_db_url(self) -> Optional[str]:
        """Получить URL для подключения к БД истории"""
        return self.database.history_db_url
    
    @property
    def auto_restore(self) -> bool:
        """Автоматически восстанавливать БД после write-тестов"""
        return self.restore.auto_restore
    
    @property
    def verify_after_restore(self) -> bool:
        """Верифицировать состояние после восстановления"""
        return self.restore.verify_after_restore
    
    @property
    def default_strategy(self) -> str:
        """Стратегия по умолчанию"""
        return self.restore.default_strategy
    
    @property
    def operation_timeout(self) -> int:
        """Таймаут на операцию backup/restore"""
        return self.restore.operation_timeout
    
    @property
    def snapshots_dir(self) -> str:
        """Директория для snapshots"""
        return self.paths.snapshots_dir
    
    @property
    def logs_dir(self) -> str:
        """Директория для логов"""
        return self.paths.logs_dir
    
    def get_snapshots_dir(self) -> Path:
        """Получить абсолютный путь к директории snapshots"""
        return Path(self.paths.snapshots_dir).resolve()
    
    def get_logs_dir(self) -> Path:
        """Получить абсолютный путь к директории логов"""
        return Path(self.paths.logs_dir).resolve()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать настройки в словарь"""
        return {
            "database": {
                "history_db_url": self.history_db_url,
            },
            "restore": {
                "default_strategy": self.restore.default_strategy,
                "auto_restore": self.restore.auto_restore,
                "verify_after_restore": self.restore.verify_after_restore,
                "large_table_warning_threshold": self.restore.large_table_warning_threshold,
                "large_table_confirm_threshold": self.restore.large_table_confirm_threshold,
                "max_restore_retries": self.restore.max_restore_retries,
                "operation_timeout": self.restore.operation_timeout,
                "backup_table_prefix": self.restore.backup_table_prefix,
                "verify_checksums": self.restore.verify_checksums,
                "checksum_max_rows": self.restore.checksum_max_rows,
            },
            "paths": {
                "snapshots_dir": self.paths.snapshots_dir,
                "logs_dir": self.paths.logs_dir,
            },
            "api": {
                "host": self.api.api_host,
                "port": self.api.api_port,
            },
            "test": {
                "default_users": self.test.default_users,
                "default_spawn_rate": self.test.default_spawn_rate,
                "default_duration": self.test.default_duration,
                "default_queries": self.test.default_queries,
            },
        }


# Глобальный экземпляр настроек
settings = Settings()


# ============================================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ
# ============================================================

# Сохраняем старый RESTORE_CONFIG для обратной совместимости
RESTORE_CONFIG: Dict[str, Any] = {
    "default_strategy": settings.restore.default_strategy,
    "auto_restore": settings.restore.auto_restore,
    "verify_after_restore": settings.restore.verify_after_restore,
    "large_table_warning_threshold": settings.restore.large_table_warning_threshold,
    "large_table_confirm_threshold": settings.restore.large_table_confirm_threshold,
    "max_restore_retries": settings.restore.max_restore_retries,
    "operation_timeout": settings.restore.operation_timeout,
    "snapshots_dir": settings.paths.snapshots_dir,
    "backup_table_prefix": settings.restore.backup_table_prefix,
    "verify_checksums": settings.restore.verify_checksums,
    "checksum_max_rows": settings.restore.checksum_max_rows,
}


def get_restore_config() -> Dict[str, Any]:
    """Получить конфигурацию отката БД (обратная совместимость)"""
    return RESTORE_CONFIG.copy()


def update_restore_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Обновить конфигурацию отката БД (обратная совместимость)"""
    global RESTORE_CONFIG
    
    # Обновляем глобальный словарь
    RESTORE_CONFIG.update(updates)
    
    # Также обновляем в singleton settings
    for key, value in updates.items():
        if hasattr(settings.restore, key):
            setattr(settings.restore, key, value)
        elif key == "snapshots_dir" and hasattr(settings.paths, key):
            setattr(settings.paths, key, value)
    
    return RESTORE_CONFIG.copy()


def reload_settings() -> Settings:
    """Перезагрузить настройки из .env файла"""
    global settings, RESTORE_CONFIG
    settings = Settings()
    
    # Обновляем RESTORE_CONFIG
    RESTORE_CONFIG = {
        "default_strategy": settings.restore.default_strategy,
        "auto_restore": settings.restore.auto_restore,
        "verify_after_restore": settings.restore.verify_after_restore,
        "large_table_warning_threshold": settings.restore.large_table_warning_threshold,
        "large_table_confirm_threshold": settings.restore.large_table_confirm_threshold,
        "max_restore_retries": settings.restore.max_restore_retries,
        "operation_timeout": settings.restore.operation_timeout,
        "snapshots_dir": settings.paths.snapshots_dir,
        "backup_table_prefix": settings.restore.backup_table_prefix,
        "verify_checksums": settings.restore.verify_checksums,
        "checksum_max_rows": settings.restore.checksum_max_rows,
    }
    
    return settings
