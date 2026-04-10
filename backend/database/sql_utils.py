"""
Общие SQL helper-функции для работы с таблицами
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


def resolve_dbms_type(engine: AsyncEngine, dbms_type: Optional[str] = None) -> str:
    """Определить тип СУБД из аргумента или engine"""
    return dbms_type or engine.dialect.name


async def get_row_count(
    engine: AsyncEngine,
    table: str,
    dbms_type: Optional[str] = None,
) -> int:
    """Получить количество строк в таблице"""
    resolved_dbms_type = resolve_dbms_type(engine, dbms_type)

    async with engine.connect() as conn:
        if resolved_dbms_type == 'postgresql':
            sql = f'SELECT COUNT(*) FROM "{table}"'
        else:
            sql = f'SELECT COUNT(*) FROM `{table}`'

        result = await conn.execute(text(sql))
        return result.scalar()


async def get_table_size(
    engine: AsyncEngine,
    table: str,
    dbms_type: Optional[str] = None,
) -> int:
    """Получить размер таблицы в байтах"""
    resolved_dbms_type = resolve_dbms_type(engine, dbms_type)

    async with engine.connect() as conn:
        if resolved_dbms_type == 'postgresql':
            sql = f"SELECT pg_total_relation_size('\"{table}\"')"
            result = await conn.execute(text(sql))
            return result.scalar() or 0

        if resolved_dbms_type == 'mysql':
            sql = """
                SELECT DATA_LENGTH + INDEX_LENGTH
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table
            """
            result = await conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            return row[0] if row else 0

    return 0
