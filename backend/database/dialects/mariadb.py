"""
MariaDB-специфичная реализация диалекта СУБД.
"""
from typing import Dict

from backend.database.dialects.mysql import MySQLDialect


class MariaDBDialect(MySQLDialect):
    """Диалект MariaDB поверх MySQL-совместимого async driver."""

    name = "mariadb"
    display_name = "MariaDB"

    def get_connection_url(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> str:
        # Для asyncio SQLAlchemy штатно поддерживает aiomysql через mysql-dialect,
        # а тип mariadb сохраняется отдельно на уровне конфигурации проекта.
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
