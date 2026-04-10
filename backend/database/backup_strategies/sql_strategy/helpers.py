"""
Вспомогательные методы для SQL Backup Strategy
"""
from typing import Any, Dict, Set, List
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.database.dialects import get_dialect
from backend.database.sql_utils import resolve_dbms_type


async def get_fk_dependencies(engine: AsyncEngine, tables: Set[str]) -> Dict[str, Set[str]]:
    """
    Получить FK зависимости между таблицами
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц для анализа
        
    Returns:
        Dict[table -> set of referenced tables]
    """
    dbms_type = resolve_dbms_type(engine)
    dialect = get_dialect(dbms_type)
    async with engine.connect() as conn:
        return await dialect.load_fk_dependencies(conn, tables)


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


async def save_auto_values(
    engine: AsyncEngine,
    tables: Set[str],
    dbms_type: str = None,
) -> Dict[str, Any]:
    """Сохранить sequence/AUTO_INCREMENT-подобные значения в DBMS-agnostic виде."""
    resolved_dbms_type = resolve_dbms_type(engine, dbms_type)
    dialect = get_dialect(resolved_dbms_type)
    async with engine.connect() as conn:
        return await dialect.save_auto_values(conn, tables)

