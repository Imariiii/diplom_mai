"""
Централизованная конфигурация системы отката баз данных

Использует Pydantic BaseSettings для управления конфигурацией через:
- Переменные окружения
- Файл .env
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Настройки подключения к базам данных"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # History database
    history_db_url: Optional[str] = Field(default=None, alias="HISTORY_DATABASE_URL")


class RestoreSettings(BaseSettings):
    """Настройки восстановления баз данных"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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


class PathSettings(BaseSettings):
    """Настройки путей"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Директория для snapshots/дампов
    snapshots_dir: str = Field(default="./snapshots")
    
    # Директория для логов
    logs_dir: str = Field(default="./logs")


class APISettings(BaseSettings):
    """Настройки API"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")


class TestSettings(BaseSettings):
    """Настройки тестирования"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_users: int = Field(default=10)
    default_spawn_rate: int = Field(default=2)
    default_duration: int = Field(default=60)
    db_pool_max_size: int = Field(default=80)
    db_pool_max_overflow: int = Field(default=0)
    default_queries: list = Field(default_factory=lambda: [
        "SELECT * FROM actor LIMIT 100",
        "SELECT * FROM film WHERE length > 120",
        "SELECT COUNT(*) FROM rental",
        "SELECT customer_id, COUNT(*) FROM rental GROUP BY customer_id"
    ])


class Settings(BaseSettings):
    """
    Главный класс настроек приложения
    
    Объединяет все настройки в единый центр конфигурации.
    Использует Pydantic BaseSettings для загрузки из переменных окружения и .env файла.
    
    Пример использования:
        from backend.core.config import settings
        
        print(settings.database.history_db_url)
        print(settings.restore.auto_restore)    # True
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Подгружаем вложенные настройки
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    restore: RestoreSettings = Field(default_factory=RestoreSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    api: APISettings = Field(default_factory=APISettings)
    test: TestSettings = Field(default_factory=TestSettings)

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
                "history_db_url": self.database.history_db_url,
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
                "db_pool_max_size": self.test.db_pool_max_size,
                "db_pool_max_overflow": self.test.db_pool_max_overflow,
                "default_queries": self.test.default_queries,
            },
        }


@dataclass
class RestoreRuntimeConfig:
    """Типизированная конфигурация восстановления для runtime-компонентов."""

    default_strategy: str
    auto_restore: bool
    verify_after_restore: bool
    large_table_warning_threshold: int
    large_table_confirm_threshold: int
    max_restore_retries: int
    operation_timeout: int
    snapshots_dir: str
    backup_table_prefix: str
    verify_checksums: bool
    checksum_max_rows: int

    @classmethod
    def from_settings(cls, app_settings: Settings) -> "RestoreRuntimeConfig":
        """Собрать runtime-конфигурацию из централизованных настроек."""
        return cls(
            default_strategy=app_settings.restore.default_strategy,
            auto_restore=app_settings.restore.auto_restore,
            verify_after_restore=app_settings.restore.verify_after_restore,
            large_table_warning_threshold=app_settings.restore.large_table_warning_threshold,
            large_table_confirm_threshold=app_settings.restore.large_table_confirm_threshold,
            max_restore_retries=app_settings.restore.max_restore_retries,
            operation_timeout=app_settings.restore.operation_timeout,
            snapshots_dir=app_settings.paths.snapshots_dir,
            backup_table_prefix=app_settings.restore.backup_table_prefix,
            verify_checksums=app_settings.restore.verify_checksums,
            checksum_max_rows=app_settings.restore.checksum_max_rows,
        )


# Глобальный экземпляр настроек
settings = Settings()
