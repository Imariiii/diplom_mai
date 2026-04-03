"""
Вспомогательные методы для SQL Backup Strategy
"""
from typing import Dict, Set, List
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text


async def get_fk_dependencies(engine: AsyncEngine, tables: Set[str]) -> Dict[str, Set[str]]:
    """
    Получить FK зависимости между таблицами
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц для анализа
        
    Returns:
        Dict[table -> set of referenced tables]
    """
    dependencies = {}
    dbms_type = engine.dialect.name
    
    async with engine.connect() as conn:
        if dbms_type == 'postgresql':
            sql = """
                SELECT 
                    tc.table_name,
                    ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            """
            result = await conn.execute(text(sql))
            
            for row in result:
                table, ref_table = row
                if table in tables and ref_table in tables:
                    if table not in dependencies:
                        dependencies[table] = set()
                    dependencies[table].add(ref_table)
                    
        elif dbms_type == 'mysql':
            sql = """
                SELECT 
                    TABLE_NAME,
                    REFERENCED_TABLE_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_NAME IS NOT NULL
                    AND TABLE_SCHEMA = DATABASE()
            """
            result = await conn.execute(text(sql))
            
            for row in result:
                table, ref_table = row
                if table in tables and ref_table in tables:
                    if table not in dependencies:
                        dependencies[table] = set()
                    dependencies[table].add(ref_table)
    
    return dependencies


def topological_sort_restore_order(tables: Set[str], dependencies: Dict[str, Set[str]]) -> List[str]:
    """
    Топологическая сортировка (алгоритм Кана) для определения порядка восстановления.
    Таблицы, на которые ссылаются другие (родительские), восстанавливаются первыми.
    
    Args:
        tables: Множество таблиц
        dependencies: Dict[table -> set of referenced tables]
        
    Returns:
        Список таблиц в порядке восстановления
    """
    # in_degree = количество таблиц, которые ссылаются на данную
    in_degree = {table: 0 for table in tables}
    
    # Вычисляем in_degree
    for table, refs in dependencies.items():
        for ref in refs:
            if ref in in_degree:
                in_degree[ref] += 1
    
    # Находим таблицы с in_degree = 0 (никто на них не ссылается)
    queue = [table for table in tables if in_degree[table] == 0]
    queue.sort()  # Детерминированный порядок
    
    result = []
    
    while queue:
        # Берём таблицу без зависимостей
        table = queue.pop(0)
        result.append(table)
        
        # Уменьшаем in_degree для таблиц, которые зависят от этой
        for dep_table, refs in dependencies.items():
            if table in refs:
                in_degree[dep_table] -= 1
                if in_degree[dep_table] == 0:
                    queue.append(dep_table)
                    queue.sort()
    
    return result


async def save_postgres_sequences(engine: AsyncEngine, tables: Set[str]) -> Dict:
    """
    Сохранить значения sequences для PostgreSQL
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц
    
    Returns:
        Dict[seq_name -> {last_value, is_called}]
    """
    sequences = {}
    
    async with engine.connect() as conn:
        for table in tables:
            # Находим primary key column с sequence
            sql = """
                SELECT column_name, 
                       pg_get_serial_sequence(:table, column_name) as seq_name
                FROM information_schema.columns
                WHERE table_name = :table
                  AND table_schema = 'public'
                  AND data_type IN ('integer', 'bigint')
                  AND column_default LIKE 'nextval%'
            """
            result = await conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            
            if row and row[1]:  # seq_name
                seq_name = row[1]
                # Получаем текущее значение sequence
                seq_result = await conn.execute(text(f"SELECT last_value, is_called FROM {seq_name}"))
                seq_row = seq_result.fetchone()
                if seq_row:
                    sequences[seq_name] = {
                        "last_value": seq_row[0],
                        "is_called": seq_row[1]
                    }
    
    return sequences


async def save_mysql_auto_increments(engine: AsyncEngine, tables: Set[str]) -> Dict:
    """
    Сохранить AUTO_INCREMENT значения для MySQL
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц
    
    Returns:
        Dict[table -> auto_increment_value]
    """
    auto_increments = {}
    
    async with engine.connect() as conn:
        for table in tables:
            sql = """
                SELECT AUTO_INCREMENT 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                  AND TABLE_NAME = :table
            """
            result = await conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            if row and row[0]:
                auto_increments[table] = row[0]
    
    return auto_increments


async def get_row_count(engine: AsyncEngine, table: str, dbms_type: str) -> int:
    """Получить количество строк в таблице"""
    async with engine.connect() as conn:
        if dbms_type == 'postgresql':
            sql = f'SELECT COUNT(*) FROM "{table}"'
        else:
            sql = f'SELECT COUNT(*) FROM `{table}`'
        
        result = await conn.execute(text(sql))
        return result.scalar()


async def get_table_size(engine: AsyncEngine, table: str, dbms_type: str) -> int:
    """Получить размер таблицы в байтах"""
    async with engine.connect() as conn:
        if dbms_type == 'postgresql':
            sql = f"SELECT pg_total_relation_size('\"{table}\"')"
            result = await conn.execute(text(sql))
            return result.scalar() or 0
        
        elif dbms_type == 'mysql':
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