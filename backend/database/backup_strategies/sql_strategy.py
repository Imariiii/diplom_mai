"""
SQL-based стратегия бэкапа через CREATE TABLE AS SELECT
Универсальная стратегия, работает через SQLAlchemy без внешних утилит

NOTE: Данный модуль сохранён для обратной совместимости.
Основная реализация находится в пакете sql_strategy/
"""

# Re-export для обратной совместимости
from backend.database.backup_strategies.sql_strategy import SqlBackupStrategy

__all__ = ['SqlBackupStrategy']
