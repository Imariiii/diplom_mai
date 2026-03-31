"""
Вспомогательные методы для SQL Backup Strategy
FK-зависимости, sequences, topological_sort
"""
from typing import Dict, Set, List
from sqlalchemy import Engine, text


async def get_fk_dependencies(engine: Engine, tables: Set[str]) -> Dict[str, Set[str]]:
    """
    Получить FK зависимости между таблицами
    
    Args:
        engine: SQLAlchemy engine
        tables: Множество таблиц для анализа
        
    Returns:
        Dict[table -> set of referenced tables]
    """
    dbms_type = engine.dialect.name
    dependencies = {}
    
    with engine.connect() as conn:
        if dbms_type == 'postgresql':
            sql = """
                SELECT 
                    tc.table_name,
                    ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu 
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name IN :tables
            """
            result = conn.execute(text(sql), {"tables": tuple(tables)})
            
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
                AND TABLE_NAME IN :tables
            """
            result = conn.execute(text(sql), {"tables": tuple(tables)})
            
            for row in result:
                table, ref_table = row
                if table in tables and ref_table in tables:
                    if table not in dependencies:
                        dependencies[table] = set()
                    dependencies[table].add(ref_table)
    
    return dependencies


def topological_sort_restore_order(tables: Set[str], dependencies: Dict[str, Set[str]]) -> List[str]:
    """
    Топологическая сортировка (алгоритм Кана) для определения порядка восстановления
    
    Таблицы, на которые ссылаются другие (родительские), восстанавливаются первыми.
    
    Args:
        tables: Множество таблиц
        dependencies: Dict[table -> set of referenced tables]
        
    Returns:
        Список таблиц в порядке восстановления
    """
    # in_degree = количество зависимостей (сколько таблиц ссылается на эту)
    in_degree = {table: 0 for table in tables}
    
    for table, refs in dependencies.items():
        for ref in refs:
            if ref in in_degree:
                # Таблица 'table' зависит от 'ref', значит ref должна быть восстановлена раньше
                in_degree[table] += 1
    
    # Находим таблицы без зависимостей (которые никто не ссылает) - они идут первыми
    queue = [t for t in tables if in_degree[t] == 0]
    result = []
    
    while queue:
        # Берём таблицу без зависимостей
        table = queue.pop(0)
        result.append(table)
        
        # Уменьшаем in_degree для таблиц, зависящих от текущей
        for t, refs in dependencies.items():
            if table in refs:
                in_degree[t] -= 1
                if in_degree[t] == 0:
                    queue.append(t)
    
    # Если остались таблицы с циклическими зависимостями
    if len(result) < len(tables):
        remaining = [t for t in tables if t not in result]
        result.extend(remaining)
    
    return result


async def save_postgres_sequences(engine: Engine, tables: Set[str]) -> Dict:
    """
    Сохранить значения sequences для PostgreSQL
    
    Args:
        engine: SQLAlchemy engine
        tables: Множество таблиц
        
    Returns:
        Dict[seq_name -> {last_value, is_called, table, column}]
    """
    sequences = {}
    
    with engine.connect() as conn:
        for table in tables:
            # Находим sequences для таблицы
            sql = """
                SELECT column_name, 
                       pg_get_serial_sequence(:table, column_name) as seq_name
                FROM information_schema.columns
                WHERE table_name = :table
                AND data_type IN ('integer', 'bigint')
            """
            result = conn.execute(text(sql), {"table": table})
            
            for row in result:
                col_name, seq_name = row
                if seq_name:
                    # Получаем текущее значение
                    seq_result = conn.execute(
                        text(f"SELECT last_value, is_called FROM {seq_name}")
                    )
                    seq_row = seq_result.fetchone()
                    if seq_row:
                        sequences[seq_name] = {
                            "last_value": seq_row[0],
                            "is_called": seq_row[1],
                            "table": table,
                            "column": col_name
                        }
    
    return sequences


async def save_mysql_auto_increments(engine: Engine, tables: Set[str]) -> Dict:
    """
    Сохранить AUTO_INCREMENT значения для MySQL
    
    Args:
        engine: SQLAlchemy engine
        tables: Множество таблиц
        
    Returns:
        Dict[table -> auto_increment_value]
    """
    auto_increments = {}
    
    with engine.connect() as conn:
        for table in tables:
            sql = """
                SELECT AUTO_INCREMENT 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table
            """
            result = conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            if row and row[0]:
                auto_increments[table] = row[0]
    
    return auto_increments


async def restore_postgres_sequences(engine: Engine, sequences: Dict) -> None:
    """Восстановить значения sequences в PostgreSQL"""
    with engine.connect() as conn:
        for seq_name, info in sequences.items():
            sql = f"SELECT setval('{seq_name}', {info['last_value']}, {str(info['is_called']).lower()})"
            conn.execute(text(sql))
        conn.commit()


async def restore_mysql_auto_increments(engine: Engine, auto_increments: Dict) -> None:
    """Восстановить AUTO_INCREMENT значения в MySQL"""
    with engine.connect() as conn:
        for table, value in auto_increments.items():
            sql = f"ALTER TABLE `{table}` AUTO_INCREMENT = {value}"
            conn.execute(text(sql))
        conn.commit()