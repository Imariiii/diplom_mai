"""
Логика восстановления для SQL Backup Strategy
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from .. import BackupInfo
from backend.database.dialects import get_dialect
from backend.database.sql_utils import resolve_dbms_type
from .helpers import get_fk_dependencies, topological_sort_restore_order


async def restore_backup_logic(
    engine: AsyncEngine,
    backup_info: BackupInfo,
    get_backup_table_name_func
) -> None:
    """
    Восстановить базу данных из бэкапа
    
    Args:
        engine: SQLAlchemy async engine
        backup_info: Информация о бэкапе
        get_backup_table_name_func: Функция для получения имени backup-таблицы
    """
    dbms_type = backup_info.dbms_type or resolve_dbms_type(engine)
    dialect = get_dialect(dbms_type)
    tables = backup_info.tables
    
    # Определяем порядок восстановления
    restore_order = await get_restore_order(engine, tables)
    
    # Используем одно соединение для всех операций восстановления
    # Это важно для MySQL, где SET FOREIGN_KEY_CHECKS сессионный
    async with engine.connect() as conn:
        # Отключаем constraints
        await conn.execute(text(dialect.get_disable_constraints_sql()))
        await conn.commit()
        
        try:
            # Восстанавливаем таблицы в правильном порядке
            for table in restore_order:
                backup_table = get_backup_table_name_func(table)
                await do_restore_table(dbms_type, table, backup_table, conn)
            
            # Восстанавливаем sequences / AUTO_INCREMENT
            auto_values = backup_info.sequences if dbms_type == 'postgresql' else backup_info.auto_increments
            if auto_values:
                await dialect.restore_auto_values(conn, auto_values)
                await conn.commit()
        finally:
            # Включаем constraints обратно
            await conn.execute(text(dialect.get_enable_constraints_sql()))
            await conn.commit()


async def get_restore_order(engine: AsyncEngine, tables: set) -> List[str]:
    """
    Определить порядок восстановления таблиц с учётом FK-зависимостей
    Таблицы, на которые ссылаются другие, восстанавливаются первыми.
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц
        
    Returns:
        Список таблиц в порядке восстановления
    """
    # Получаем FK зависимости
    dependencies = await get_fk_dependencies(engine, tables)
    
    # Топологическая сортировка
    return topological_sort_restore_order(tables, dependencies)


async def restore_table(
    engine: AsyncEngine,
    table: str,
    backup_table: str,
    conn=None
) -> None:
    """Восстановить одну таблицу из бэкапа"""
    dbms_type = resolve_dbms_type(engine)
    
    # Используем переданное соединение или создаём новое
    if conn is None:
        async with engine.connect() as new_conn:
            await do_restore_table(dbms_type, table, backup_table, new_conn)
    else:
        await do_restore_table(dbms_type, table, backup_table, conn)


async def do_restore_table(dbms_type: str, table: str, backup_table: str, conn) -> None:
    """
    Внутренний метод восстановления таблицы
    
    Args:
        dbms_type: Тип СУБД ('postgresql' или 'mysql')
        table: Имя таблицы для восстановления
        backup_table: Имя backup-таблицы
        conn: Активное соединение с БД
    """
    dialect = get_dialect(dbms_type)
    await conn.execute(text(dialect.get_truncate_table_sql(table)))
    await conn.commit()  # Commit после TRUNCATE для MySQL
    
    await conn.execute(text(dialect.get_insert_from_backup_sql(table, backup_table)))
    await conn.commit()


async def disable_constraints(engine: AsyncEngine, dbms_type: str) -> None:
    """Отключить FK constraints"""
    dialect = get_dialect(dbms_type)
    async with engine.connect() as conn:
        await conn.execute(text(dialect.get_disable_constraints_sql()))
        await conn.commit()


async def enable_constraints(engine: AsyncEngine, dbms_type: str) -> None:
    """Включить FK constraints"""
    dialect = get_dialect(dbms_type)
    async with engine.connect() as conn:
        await conn.execute(text(dialect.get_enable_constraints_sql()))
        await conn.commit()