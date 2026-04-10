"""
Общие SQL helper-функции для работы с таблицами
"""
from weakref import WeakKeyDictionary
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.database.dialects import get_dialect

_ENGINE_DBMS_TYPES: "WeakKeyDictionary[AsyncEngine, str]" = WeakKeyDictionary()


def register_engine_dbms_type(engine: AsyncEngine, dbms_type: str) -> None:
    """Связать созданный engine с логическим типом СУБД проекта."""
    _ENGINE_DBMS_TYPES[engine] = dbms_type


def resolve_dbms_type(engine: AsyncEngine, dbms_type: Optional[str] = None) -> str:
    """Определить тип СУБД из аргумента или engine"""
    if dbms_type:
        return dbms_type

    engine_dbms_type = _ENGINE_DBMS_TYPES.get(engine)
    if engine_dbms_type:
        return engine_dbms_type

    dialect = engine.sync_engine.dialect
    if dialect.name == "mysql" and getattr(dialect, "is_mariadb", False):
        return "mariadb"

    return dialect.name


async def get_row_count(
    engine: AsyncEngine,
    table: str,
    dbms_type: Optional[str] = None,
) -> int:
    """Получить количество строк в таблице"""
    resolved_dbms_type = resolve_dbms_type(engine, dbms_type)
    dialect = get_dialect(resolved_dbms_type)

    async with engine.connect() as conn:
        result = await conn.execute(text(dialect.get_row_count_sql(table)))
        return result.scalar()


async def get_table_size(
    engine: AsyncEngine,
    table: str,
    dbms_type: Optional[str] = None,
) -> int:
    """Получить размер таблицы в байтах"""
    resolved_dbms_type = resolve_dbms_type(engine, dbms_type)
    dialect = get_dialect(resolved_dbms_type)

    async with engine.connect() as conn:
        result = await conn.execute(text(dialect.get_table_size_sql(table)))
        row = result.fetchone()
        if row:
            return row[0] or 0

    return 0
