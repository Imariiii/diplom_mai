"""
SQL-based стратегия бэкапа через CREATE TABLE AS SELECT
Универсальная стратегия, работает через SQLAlchemy без внешних утилит
"""
import uuid
from typing import Dict, Set, List
from sqlalchemy import Engine, text

from . import BackupStrategy, BackupInfo, SizeEstimate


class SqlBackupStrategy(BackupStrategy):
    """
    SQL-based стратегия бэкапа
    
    Создаёт копии таблиц через CREATE TABLE ... AS SELECT *
    Поддерживает PostgreSQL и MySQL
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self._locks = {}  # Блокировки для каждой БД
    
    async def create_backup(self, engine: Engine, tables: Set[str]) -> BackupInfo:
        """Создать бэкап таблиц через CREATE TABLE AS SELECT"""
        backup_id = str(uuid.uuid4())[:8]
        dbms_type = engine.dialect.name
        
        backup_tables = set()
        row_counts = {}
        sequences = {}
        auto_increments = {}
        
        # Создаём бэкапы таблиц
        for table in tables:
            backup_table = self.get_backup_table_name(table)
            backup_tables.add(backup_table)
            
            # Удаляем старую backup-таблицу если существует
            await self._drop_table_if_exists(engine, backup_table)
            
            # Создаём backup
            row_count = await self._create_table_backup(engine, table, backup_table)
            row_counts[table] = row_count
        
        # Сохраняем sequences (PostgreSQL) или AUTO_INCREMENT (MySQL)
        if dbms_type == 'postgresql':
            sequences = await self._save_postgres_sequences(engine, tables)
        elif dbms_type == 'mysql':
            auto_increments = await self._save_mysql_auto_increments(engine, tables)
        
        return BackupInfo(
            backup_id=backup_id,
            dbms_type=dbms_type,
            tables=tables,
            backup_tables=backup_tables,
            row_counts=row_counts,
            sequences=sequences,
            auto_increments=auto_increments
        )
    
    async def restore_backup(self, engine: Engine, backup_info: BackupInfo) -> None:
        """Восстановить базу данных из бэкапа"""
        dbms_type = engine.dialect.name
        tables = backup_info.tables
        
        # Определяем порядок восстановления
        restore_order = await self._get_restore_order(engine, tables)
        
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
                    backup_table = self.get_backup_table_name(table)
                    await self._do_restore_table(dbms_type, table, backup_table, conn)
                
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
    
    async def cleanup(self, engine: Engine, backup_info: BackupInfo) -> None:
        """Удалить backup-таблицы"""
        for table in backup_info.tables:
            backup_table = self.get_backup_table_name(table)
            await self._drop_table_if_exists(engine, backup_table)
    
    async def estimate_size(self, engine: Engine, tables: Set[str]) -> SizeEstimate:
        """Оценить размер бэкапа"""
        dbms_type = engine.dialect.name
        table_info = {}
        total_rows = 0
        total_size = 0
        warnings = []
        
        warning_threshold = self.config.get("large_table_warning_threshold", 1_000_000)
        confirm_threshold = self.config.get("large_table_confirm_threshold", 10_000_000)
        
        for table in tables:
            # Получаем количество строк
            row_count = await self._get_row_count(engine, table)
            
            # Получаем размер таблицы
            size_bytes = await self._get_table_size(engine, table)
            
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
    
    # ==================== Вспомогательные методы ====================
    
    async def _create_table_backup(self, engine: Engine, table: str, backup_table: str) -> int:
        """Создать backup таблицы через CREATE TABLE AS SELECT"""
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
    
    async def _drop_table_if_exists(self, engine: Engine, table: str) -> None:
        """Удалить таблицу если существует"""
        with engine.connect() as conn:
            # Учитываем различия в синтаксисе DROP
            if engine.dialect.name == 'postgresql':
                sql = f'DROP TABLE IF EXISTS "{table}" CASCADE'
            else:
                sql = f'DROP TABLE IF EXISTS `{table}`'
            
            conn.execute(text(sql))
            conn.commit()
    
    async def _restore_table(self, engine: Engine, table: str, backup_table: str, conn=None) -> None:
        """Восстановить одну таблицу из бэкапа"""
        dbms_type = engine.dialect.name
        
        # Используем переданное соединение или создаём новое
        if conn is None:
            with engine.connect() as new_conn:
                await self._do_restore_table(dbms_type, table, backup_table, new_conn)
        else:
            await self._do_restore_table(dbms_type, table, backup_table, conn)
    
    async def _do_restore_table(self, dbms_type: str, table: str, backup_table: str, conn) -> None:
        """Внутренний метод восстановления таблицы"""
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
    
    async def _get_restore_order(self, engine: Engine, tables: Set[str]) -> List[str]:
        """
        Определить порядок восстановления таблиц с учётом FK-зависимостей
        Таблицы, на которые ссылаются другие, восстанавливаются первыми
        """
        dbms_type = engine.dialect.name
        
        # Получаем FK зависимости
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
        
        # Топологическая сортировка (Kahn's algorithm)
        # Таблицы без зависимостей идут первыми
        in_degree = {table: 0 for table in tables}
        
        for table, refs in dependencies.items():
            for ref in refs:
                if ref in in_degree:
                    in_degree[table] += 1
        
        # Находим таблицы без зависимостей
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
    
    # ==================== PostgreSQL специфичные методы ====================
    
    async def _disable_postgres_constraints(self, engine: Engine) -> None:
        """Отключить FK constraints и triggers в PostgreSQL"""
        with engine.connect() as conn:
            conn.execute(text("SET session_replication_role = 'replica'"))
            conn.commit()
    
    async def _enable_postgres_constraints(self, engine: Engine) -> None:
        """Включить FK constraints и triggers в PostgreSQL"""
        with engine.connect() as conn:
            conn.execute(text("SET session_replication_role = 'origin'"))
            conn.commit()
    
    async def _save_postgres_sequences(self, engine: Engine, tables: Set[str]) -> Dict:
        """Сохранить значения sequences для PostgreSQL"""
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
    
    async def _restore_postgres_sequences(self, engine: Engine, sequences: Dict) -> None:
        """Восстановить значения sequences в PostgreSQL"""
        with engine.connect() as conn:
            for seq_name, info in sequences.items():
                sql = f"SELECT setval('{seq_name}', {info['last_value']}, {str(info['is_called']).lower()})"
                conn.execute(text(sql))
            conn.commit()
    
    # ==================== MySQL специфичные методы ====================
    
    async def _disable_mysql_constraints(self, engine: Engine) -> None:
        """Отключить FK constraints в MySQL"""
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.commit()
    
    async def _enable_mysql_constraints(self, engine: Engine) -> None:
        """Включить FK constraints в MySQL"""
        with engine.connect() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            conn.commit()
    
    async def _save_mysql_auto_increments(self, engine: Engine, tables: Set[str]) -> Dict:
        """Сохранить AUTO_INCREMENT значения для MySQL"""
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
    
    async def _restore_mysql_auto_increments(self, engine: Engine, auto_increments: Dict) -> None:
        """Восстановить AUTO_INCREMENT значения в MySQL"""
        with engine.connect() as conn:
            for table, value in auto_increments.items():
                sql = f"ALTER TABLE `{table}` AUTO_INCREMENT = {value}"
                conn.execute(text(sql))
            conn.commit()
    
    # ==================== Общие методы ====================
    
    async def _get_row_count(self, engine: Engine, table: str) -> int:
        """Получить количество строк в таблице"""
        with engine.connect() as conn:
            dbms_type = engine.dialect.name
            if dbms_type == 'postgresql':
                sql = f'SELECT COUNT(*) FROM "{table}"'
            else:
                sql = f'SELECT COUNT(*) FROM `{table}`'
            
            result = conn.execute(text(sql))
            return result.scalar()
    
    async def _get_table_size(self, engine: Engine, table: str) -> int:
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
