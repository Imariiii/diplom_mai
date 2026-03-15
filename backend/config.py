"""
Конфигурация системы отката баз данных
"""
import os
from typing import Dict, Any

# Конфигурация отката БД
RESTORE_CONFIG: Dict[str, Any] = {
    # Стратегия по умолчанию: "sql" или "native"
    "default_strategy": "sql",
    
    # Автоматически восстанавливать БД после write-тестов
    "auto_restore": True,
    
    # Верифицировать состояние после восстановления
    "verify_after_restore": True,
    
    # Порог предупреждения: если таблица больше N строк — предупредить
    "large_table_warning_threshold": 1_000_000,
    
    # Порог запрета: если таблица больше N строк — требовать подтверждение
    "large_table_confirm_threshold": 10_000_000,
    
    # Максимальное количество retry при неудачном restore
    "max_restore_retries": 2,
    
    # Таймаут на операцию backup/restore (секунды)
    "operation_timeout": 300,
    
    # Директория для native-дампов
    "snapshots_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshots"),
    
    # Префикс для backup-таблиц в SQL-стратегии
    "backup_table_prefix": "_loadtest_backup_",
    
    # Включить чексуммы при верификации (медленнее, но надёжнее)
    "verify_checksums": False,
    
    # Максимальный размер таблицы для чексуммы (строк)
    "checksum_max_rows": 100_000,
}


def get_restore_config() -> Dict[str, Any]:
    """Получить конфигурацию отката БД"""
    return RESTORE_CONFIG.copy()


def update_restore_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Обновить конфигурацию отката БД"""
    RESTORE_CONFIG.update(updates)
    return RESTORE_CONFIG.copy()
