"""
Реестр поддерживаемых диалектов СУБД.
"""
from typing import Dict, List

from backend.database.dialects.base import DbmsDialect
from backend.database.dialects.mariadb import MariaDBDialect
from backend.database.dialects.mysql import MySQLDialect
from backend.database.dialects.postgresql import PostgreSQLDialect


_REGISTRY: Dict[str, DbmsDialect] = {}


def register_dialect(dialect: DbmsDialect) -> None:
    """Зарегистрировать диалект СУБД."""
    _REGISTRY[dialect.name] = dialect


def get_dialect(dbms_type: str) -> DbmsDialect:
    """Получить зарегистрированный диалект по имени."""
    dialect = _REGISTRY.get(dbms_type)
    if not dialect:
        raise ValueError(f"Неподдерживаемый тип БД: {dbms_type}")
    return dialect


def is_registered_dbms_type(dbms_type: str) -> bool:
    """Проверить, поддерживается ли указанный тип СУБД."""
    return dbms_type in _REGISTRY


def supported_dbms_types() -> List[str]:
    """Получить список поддерживаемых типов СУБД."""
    return list(_REGISTRY.keys())


register_dialect(PostgreSQLDialect())
register_dialect(MySQLDialect())
register_dialect(MariaDBDialect())


__all__ = [
    "DbmsDialect",
    "get_dialect",
    "is_registered_dbms_type",
    "register_dialect",
    "supported_dbms_types",
]
