"""
Логика создания backup для SQL Backup Strategy
"""
import uuid
from typing import Dict, Set, List
from sqlalchemy import Engine, text

from .. import BackupInfo, SizeEstimate
from .helpers import save_postgres_sequences, save_mysql_auto_increments


async def create_backup_logic(
    engine: Engine,
    tables: Set[str],
    get_backup_table_name_func,
    config: Dict
) -> BackupInfo:
    """
    Логика создания бэкапа таблиц через CREATE TABLE AS SELECT
    
    Args:
        engine: SQLAlchemy engine
        tables: Множество таблиц для бэкапа
        get_backup_table_name_func: Функция для получения имени backup-таблицы
        config: Конфигурация стратегии
        
    Returns:
        BackupInfo с информацией о созданном бэкапе
    """
    backup_id = str(uuid.uuid4())[:8]
    dbms_type = engine.dialect.name
    
    backup_tables = set()
    row_counts = {}
    sequences = {}
    auto_increments = {}
    
    # Создаём бэкапы таблиц
    for table in tables:
        backup_table = get_backup_table_name_func(table)
        backup_tables.add(backup_table)
        
        # Удаляем старую backup-таблицу если существует
        await drop_table_if_exists(engine, backup_table)
        
        # Создаём backup
        row_count = await create_table_backup(engine, table, backup_table)
        row_counts[table] = row_count
    
    # Сохраняем sequences (PostgreSQL) или AUTO_INCREMENT (MySQL)
    if dbms_type == 'postgresql':
        sequences = await save_postgres_sequences(engine, tables)
    elif dbms_type == 'mysql':
        auto_increments = await save_mysql_auto_increments(engine, tables)
    
    return BackupInfo(
        backup_id=backup_id,
        dbms_type=dbms_type,
        tables=tables,
        backup_tables=backup_tables,
        row_counts=row_counts,
        sequences=sequences,
        auto_increments=auto_increments
    )


async def create_table_backup(engine: Engine, table: str, backup_table: str) -> int:
    """
    Создать backup таблицы через CREATE TABLE AS SELECT
    
    Args:
        engine: SQLAlchemy engine
        table: Исходная таблица
        backup_table: Имя backup-таблицы
        
    Returns:
        Количество скопированных строк
    """
    with engine.connect() as conn:
        dbms_type = engine.dialect.name
        
        # Создаём копию таблицы с учётом синтаксиса БД
        if dbms_type == 'postgresql':
            sql = f'CREATE TABLE "{backup_table}" AS SELECT * FROM "{table}"'
        else:
            sql = f'CREATE TABLE `{backup_table}` AS SELECT * FROM `{table}`'
        
        conn.execute(text(sql))
        conn.commit()
        
        # Получаем количество строк
        if dbms_type == 'postgresql':
            result = conn.execute(text(f'SELECT COUNT(*) FROM "{backup_table}"'))
        else:
            result = conn.execute(text(f'SELECT COUNT(*) FROM `{backup_table}`'))
        
        row_count = result.scalar()
        
        return row_count


async def drop_table_if_exists(engine: Engine, table: str) -> None:
    """Удалить таблицу если существует"""
    with engine.connect() as conn:
        # Учитываем различия в синтаксисе DROP
        if engine.dialect.name == 'postgresql':
            sql = f'DROP TABLE IF EXISTS "{table}" CASCADE'
        else:
            sql = f'DROP TABLE IF EXISTS `{table}`'
        
        conn.execute(text(sql))
        conn.commit()


async def cleanup_backup(engine: Engine, tables: Set[str], get_backup_table_name_func) -> None:
    """Удалить backup-таблицы"""
    for table in tables:
        backup_table = get_backup_table_name_func(table)
        await drop_table_if_exists(engine, backup_table)


async def estimate_size_logic(
    engine: Engine,
    tables: Set[str],
    config: Dict
) -> SizeEstimate:
    """
    Оценить размер бэкапа
    
    Args:
        engine: SQLAlchemy engine
        tables: Множество таблиц
        config: Конфигурация стратегии
        
    Returns:
        SizeEstimate с оценкой размера и времени
    """
    dbms_type = engine.dialect.name
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


async def get_row_count(engine: Engine, table: str) -> int:
    """Получить количество строк в таблице"""
    with engine.connect() as conn:
        dbms_type = engine.dialect.name
        if dbms_type == 'postgresql':
            sql = f'SELECT COUNT(*) FROM "{table}"'
        else:
            sql = f'SELECT COUNT(*) FROM `{table}`'
        
        result = conn.execute(text(sql))
        return result.scalar()


async def get_table_size(engine: Engine, table: str) -> int:
    """Получить размер таблицы в байтах"""
    dbms_type = engine.dialect.name
    
    with engine.connect() as conn:
        if dbms_type == 'postgresql':
            sql = f"SELECT pg_total_relation_size('\"{table}\"')"
            result = conn.execute(text(sql))
            return result.scalar() or 0
        
        elif dbms_type == 'mysql':
            sql = """
                SELECT DATA_LENGTH + INDEX_LENGTH 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table
            """
            result = conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            return row[0] if row else 0
        
        return 0