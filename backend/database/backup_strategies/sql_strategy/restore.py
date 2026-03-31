"""
Логика восстановления для SQL Backup Strategy
"""
from typing import List
from sqlalchemy import Engine, text

from .. import BackupInfo
from .helpers import (
    get_fk_dependencies,
    topological_sort_restore_order,
    restore_postgres_sequences,
    restore_mysql_auto_increments
)


async def restore_backup_logic(
    engine: Engine,
    backup_info: BackupInfo,
    get_backup_table_name_func
) -> None:
    """
    Восстановить базу данных из бэкапа
    
    Args:
        engine: SQLAlchemy engine
        backup_info: Информация о бэкапе
        get_backup_table_name_func: Функция для получения имени backup-таблицы
    """
    dbms_type = engine.dialect.name
    tables = backup_info.tables
    
    # Определяем порядок восстановления
    restore_order = await get_restore_order(engine, tables)
    
    # Используем одно соединение для всех операций восстановления
    # Это важно для MySQL, где SET FOREIGN_KEY_CHECKS сессионный
    with engine.connect() as conn:
        # Отключаем constraints
        if dbms_type == 'postgresql':
            conn.execute(text("SET session_replication_role = 'replica'"))
        elif dbms_type == 'mysql':
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        conn.commit()
        
        try:
            # Восстанавливаем таблицы в правильном порядке
            for table in restore_order:
                backup_table = get_backup_table_name_func(table)
                await do_restore_table(dbms_type, table, backup_table, conn)
            
            # Восстанавливаем sequences / AUTO_INCREMENT
            if dbms_type == 'postgresql' and backup_info.sequences:
                for seq_name, info in backup_info.sequences.items():
                    sql = f"SELECT setval('{seq_name}', {info['last_value']}, {str(info['is_called']).lower()})"
                    conn.execute(text(sql))
                conn.commit()
            elif dbms_type == 'mysql' and backup_info.auto_increments:
                for table, value in backup_info.auto_increments.items():
                    sql = f"ALTER TABLE `{table}` AUTO_INCREMENT = {value}"
                    conn.execute(text(sql))
                conn.commit()
        finally:
            # Включаем constraints обратно
            if dbms_type == 'postgresql':
                conn.execute(text("SET session_replication_role = 'origin'"))
            elif dbms_type == 'mysql':
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()


async def get_restore_order(engine: Engine, tables: set) -> List[str]:
    """
    Определить порядок восстановления таблиц с учётом FK-зависимостей
    Таблицы, на которые ссылаются другие, восстанавливаются первыми
    """
    # Получаем FK зависимости
    dependencies = await get_fk_dependencies(engine, tables)
    
    # Топологическая сортировка
    return topological_sort_restore_order(tables, dependencies)


async def restore_table(
    engine: Engine,
    table: str,
    backup_table: str,
    conn=None
) -> None:
    """Восстановить одну таблицу из бэкапа"""
    dbms_type = engine.dialect.name
    
    # Используем переданное соединение или создаём новое
    if conn is None:
        with engine.connect() as new_conn:
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
    # Очищаем таблицу
    if dbms_type == 'postgresql':
        conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
    else:
        conn.execute(text(f'TRUNCATE TABLE `{table}`'))
    conn.commit()  # Commit после TRUNCATE для MySQL
    
    # Вставляем данные из backup
    if dbms_type == 'postgresql':
        sql = f'INSERT INTO "{table}" SELECT * FROM "{backup_table}"'
    else:
        sql = f'INSERT INTO `{table}` SELECT * FROM `{backup_table}`'
    
    conn.execute(text(sql))
    conn.commit()


async def disable_constraints(engine: Engine, dbms_type: str) -> None:
    """Отключить FK constraints"""
    with engine.connect() as conn:
        if dbms_type == 'postgresql':
            conn.execute(text("SET session_replication_role = 'replica'"))
        elif dbms_type == 'mysql':
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.commit()


async def enable_constraints(engine: Engine, dbms_type: str) -> None:
    """Включить FK constraints"""
    with engine.connect() as conn:
        if dbms_type == 'postgresql':
            conn.execute(text("SET session_replication_role = 'origin'"))
        elif dbms_type == 'mysql':
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()