"""
Логика создания backup для SQL Backup Strategy
"""
import uuid
from typing import Dict, Set, List
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from .. import BackupInfo, SizeEstimate
from .helpers import save_auto_values
from backend.database.dialects import get_dialect
from backend.database.sql_utils import get_row_count, get_table_size, resolve_dbms_type


async def create_backup_logic(
    engine: AsyncEngine,
    tables: Set[str],
    get_backup_table_name_func,
    config: Dict
) -> BackupInfo:
    """
    Логика создания бэкапа таблиц через CREATE TABLE AS SELECT
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц для бэкапа
        get_backup_table_name_func: Функция для получения имени backup-таблицы
        config: Конфигурация стратегии
        
    Returns:
        BackupInfo с информацией о созданном бэкапе
    """
    backup_id = str(uuid.uuid4())[:8]
    dbms_type = resolve_dbms_type(engine)
    dialect = get_dialect(dbms_type)
    
    backup_tables = set()
    row_counts = {}
    sequences = {}
    auto_increments = {}
    
    if disable_sql := dialect.get_disable_strict_mode_sql():
        print(f"[BACKUP:SQL] [{dbms_type}] Отключение strict sql_mode для сессии")

    async with engine.connect() as conn:
        disable_sql = dialect.get_disable_strict_mode_sql()
        enable_sql = dialect.get_enable_strict_mode_sql()
        if disable_sql:
            await conn.execute(text(disable_sql))
            await conn.commit()
        
        try:
            for idx, table in enumerate(sorted(tables), 1):
                backup_table = get_backup_table_name_func(table)
                backup_tables.add(backup_table)
                
                await conn.execute(text(dialect.get_drop_table_sql(backup_table, cascade=True)))
                await conn.commit()
                
                await conn.execute(text(dialect.get_create_backup_table_sql(table, backup_table)))
                await conn.commit()
                
                result = await conn.execute(text(dialect.get_row_count_sql(backup_table)))
                row_counts[table] = result.scalar()
                print(
                    f"[BACKUP:SQL] [{dbms_type}] [{idx}/{len(tables)}] "
                    f"{table} → {backup_table} ({row_counts[table]:,} строк)"
                )
        finally:
            if enable_sql:
                await conn.execute(text(enable_sql))
                await conn.commit()
                print(f"[BACKUP:SQL] [{dbms_type}] Восстановление strict sql_mode")
    
    auto_values = await save_auto_values(engine, tables, dbms_type)
    if dbms_type == 'postgresql':
        sequences = auto_values
        if sequences:
            print(f"[BACKUP:SQL] [{dbms_type}] Сохранены sequences для {len(sequences)} таблиц")
    else:
        auto_increments = auto_values
        if auto_increments:
            print(f"[BACKUP:SQL] [{dbms_type}] Сохранены AUTO_INCREMENT для {len(auto_increments)} таблиц")
    
    return BackupInfo(
        backup_id=backup_id,
        dbms_type=dbms_type,
        tables=tables,
        backup_tables=backup_tables,
        row_counts=row_counts,
        strategy_name="sql",
        sequences=sequences,
        auto_increments=auto_increments
    )


async def create_table_backup(engine: AsyncEngine, table: str, backup_table: str) -> int:
    """
    Создать backup таблицы через CREATE TABLE AS SELECT
    
    Args:
        engine: SQLAlchemy async engine
        table: Исходная таблица
        backup_table: Имя backup-таблицы
        
    Returns:
        Количество скопированных строк
    """
    dialect = get_dialect(resolve_dbms_type(engine))
    async with engine.connect() as conn:
        disable_sql = dialect.get_disable_strict_mode_sql()
        enable_sql = dialect.get_enable_strict_mode_sql()
        if disable_sql:
            await conn.execute(text(disable_sql))
            await conn.commit()
        
        try:
            await conn.execute(text(dialect.get_create_backup_table_sql(table, backup_table)))
            await conn.commit()
            
            result = await conn.execute(text(dialect.get_row_count_sql(backup_table)))
            row_count = result.scalar()
        finally:
            if enable_sql:
                await conn.execute(text(enable_sql))
                await conn.commit()
        
        return row_count


async def drop_table_if_exists(engine: AsyncEngine, table: str) -> None:
    """Удалить таблицу если существует"""
    dialect = get_dialect(resolve_dbms_type(engine))
    async with engine.connect() as conn:
        await conn.execute(text(dialect.get_drop_table_sql(table, cascade=True)))
        await conn.commit()


async def cleanup_backup(engine: AsyncEngine, tables: Set[str], get_backup_table_name_func) -> None:
    """Удалить backup-таблицы"""
    for table in tables:
        backup_table = get_backup_table_name_func(table)
        await drop_table_if_exists(engine, backup_table)


async def estimate_size_logic(
    engine: AsyncEngine,
    tables: Set[str],
    config: Dict
) -> SizeEstimate:
    """
    Оценить размер бэкапа
    
    Args:
        engine: SQLAlchemy async engine
        tables: Множество таблиц
        config: Конфигурация стратегии
        
    Returns:
        SizeEstimate с оценкой размера и времени
    """
    table_info = {}
    total_rows = 0
    total_size = 0
    warnings = []
    
    warning_threshold = config.get("large_table_warning_threshold", 1_000_000)
    confirm_threshold = config.get("large_table_confirm_threshold", 10_000_000)
    
    for table in tables:
        # Получаем количество строк
        row_count = await get_row_count(engine, table)
        
        # Получаем размер таблицы
        size_bytes = await get_table_size(engine, table)
        
        table_info[table] = {
            "rows": row_count,
            "size_bytes": size_bytes
        }
        
        total_rows += row_count
        total_size += size_bytes
        
        # Формируем предупреждения
        if row_count > confirm_threshold:
            warnings.append(
                f"Very large table {table} ({row_count:,} rows, ~{size_bytes/1024/1024:.1f}MB). "
                f"Consider excluding this table or using native dump strategy."
            )
        elif row_count > warning_threshold:
            warnings.append(
                f"Large table {table} ({row_count:,} rows). "
                f"Backup will take some time."
            )
    
    # Эвристика для оценки времени
    # Примерно 1000 rows/sec для INSERT
    estimated_time = max(total_rows / 1000, 0.1)
    
    return SizeEstimate(
        tables=table_info,
        total_rows=total_rows,
        total_size_bytes=total_size,
        estimated_backup_time_sec=estimated_time,
        warnings=warnings
    )

