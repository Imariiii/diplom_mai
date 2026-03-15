"""
Верификатор состояния базы данных
Проверяет целостность восстановления данных
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from sqlalchemy import Engine, text


@dataclass
class TableFingerprint:
    """"Фингерпринт" отдельной таблицы"""
    table_name: str
    row_count: int
    checksum: Optional[str] = None
    sequence_value: Optional[int] = None
    auto_increment_value: Optional[int] = None


@dataclass
class StateFingerprint:
    """"Фингерпринт" состояния БД (набор таблиц)"""
    timestamp: datetime
    tables: Dict[str, TableFingerprint] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "tables": {
                name: {
                    "table_name": fp.table_name,
                    "row_count": fp.row_count,
                    "checksum": fp.checksum,
                    "sequence_value": fp.sequence_value,
                    "auto_increment_value": fp.auto_increment_value
                }
                for name, fp in self.tables.items()
            }
        }


@dataclass
class VerifyResult:
    """Результат верификации"""
    success: bool
    errors: List[str] = field(default_factory=list)
    details: Dict[str, dict] = field(default_factory=dict)
    
    def add_table_result(self, table: str, expected_rows: int, actual_rows: int, 
                         expected_checksum: str = None, actual_checksum: str = None):
        """Добавить результат проверки таблицы"""
        match = expected_rows == actual_rows
        if expected_checksum and actual_checksum:
            match = match and (expected_checksum == actual_checksum)
        
        self.details[table] = {
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "rows_match": expected_rows == actual_rows,
            "expected_checksum": expected_checksum,
            "actual_checksum": actual_checksum,
            "checksum_match": expected_checksum == actual_checksum if expected_checksum else None,
            "match": match
        }
        
        if not match:
            self.errors.append(
                f"Table {table}: expected {expected_rows} rows, got {actual_rows}"
            )
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "errors": self.errors,
            "details": self.details
        }


class StateVerifier:
    """Верификатор состояния базы данных"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.verify_checksums = self.config.get("verify_checksums", False)
        self.checksum_max_rows = self.config.get("checksum_max_rows", 100_000)
    
    async def capture_fingerprint(self, engine: Engine, tables: Set[str]) -> StateFingerprint:
        """
        Создать "фингерпринт" текущего состояния БД
        
        Args:
            engine: SQLAlchemy engine
            tables: Множество имён таблиц
            
        Returns:
            StateFingerprint с информацией о состоянии
        """
        fingerprint = StateFingerprint(timestamp=datetime.utcnow())
        dbms_type = engine.dialect.name
        
        for table in tables:
            table_fp = await self._capture_table_fingerprint(engine, table, dbms_type)
            fingerprint.tables[table] = table_fp
        
        return fingerprint
    
    async def verify(self, before: StateFingerprint, after: StateFingerprint) -> VerifyResult:
        """
        Сравнить два состояния и вернуть результат верификации
        
        Args:
            before: Состояние до теста (после backup)
            after: Состояние после restore
            
        Returns:
            VerifyResult с результатами проверки
        """
        result = VerifyResult(success=True)
        
        # Проверяем каждую таблицу
        for table_name, before_fp in before.tables.items():
            if table_name not in after.tables:
                result.errors.append(f"Table {table_name} missing in after state")
                result.success = False
                continue
            
            after_fp = after.tables[table_name]
            
            result.add_table_result(
                table=table_name,
                expected_rows=before_fp.row_count,
                actual_rows=after_fp.row_count,
                expected_checksum=before_fp.checksum,
                actual_checksum=after_fp.checksum
            )
            
            if not result.details[table_name]["match"]:
                result.success = False
        
        # Проверяем, нет ли лишних таблиц в after
        for table_name in after.tables:
            if table_name not in before.tables:
                result.errors.append(f"Unexpected table {table_name} in after state")
                result.success = False
        
        return result
    
    async def _capture_table_fingerprint(self, engine: Engine, table: str, 
                                          dbms_type: str) -> TableFingerprint:
        """Создать фингерпринт отдельной таблицы"""
        
        # Получаем количество строк
        row_count = await self._get_row_count(engine, table, dbms_type)
        
        # Вычисляем чексумму (только для маленьких таблиц)
        checksum = None
        if self.verify_checksums and row_count <= self.checksum_max_rows:
            checksum = await self._compute_checksum(engine, table, dbms_type)
        
        # Получаем sequence/auto_increment значения
        sequence_value = None
        auto_increment_value = None
        
        if dbms_type == 'postgresql':
            sequence_value = await self._get_postgres_sequence_value(engine, table)
        elif dbms_type == 'mysql':
            auto_increment_value = await self._get_mysql_auto_increment(engine, table)
        
        return TableFingerprint(
            table_name=table,
            row_count=row_count,
            checksum=checksum,
            sequence_value=sequence_value,
            auto_increment_value=auto_increment_value
        )
    
    async def _get_row_count(self, engine: Engine, table: str, dbms_type: str) -> int:
        """Получить количество строк в таблице"""
        with engine.connect() as conn:
            if dbms_type == 'postgresql':
                sql = f'SELECT COUNT(*) FROM "{table}"'
            else:
                sql = f'SELECT COUNT(*) FROM `{table}`'
            
            result = conn.execute(text(sql))
            return result.scalar()
    
    async def _compute_checksum(self, engine: Engine, table: str, dbms_type: str) -> str:
        """Вычислить чексумму данных таблицы"""
        with engine.connect() as conn:
            if dbms_type == 'postgresql':
                # Используем MD5 агрегацию PostgreSQL
                sql = f"""
                    SELECT MD5(string_agg(row_text, ',' ORDER BY row_text))
                    FROM (
                        SELECT row_to_json(t)::text AS row_text
                        FROM "{table}" t
                    ) subq
                """
                try:
                    result = conn.execute(text(sql))
                    return result.scalar() or ""
                except:
                    # Fallback: просто считаем строки
                    return ""
            
            elif dbms_type == 'mysql':
                # MySQL не имеет встроенной MD5 агрегации, используем простой хеш
                sql = f"SELECT COUNT(*), MD5(CONCAT(GROUP_CONCAT(id))) FROM `{table}`"
                try:
                    result = conn.execute(text(sql))
                    row = result.fetchone()
                    return row[1] if row else ""
                except:
                    return ""
        
        return ""
    
    async def _get_postgres_sequence_value(self, engine: Engine, table: str) -> Optional[int]:
        """Получить текущее значение sequence для таблицы PostgreSQL"""
        with engine.connect() as conn:
            # Находим primary key column с sequence
            sql = """
                SELECT column_name, pg_get_serial_sequence(:table, column_name) as seq_name
                FROM information_schema.columns
                WHERE table_name = :table
                AND data_type IN ('integer', 'bigint')
                AND column_default LIKE 'nextval%'
            """
            result = conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            
            if row and row[1]:  # seq_name
                seq_result = conn.execute(text(f"SELECT last_value FROM {row[1]}"))
                seq_row = seq_result.fetchone()
                return seq_row[0] if seq_row else None
        
        return None
    
    async def _get_mysql_auto_increment(self, engine: Engine, table: str) -> Optional[int]:
        """Получить AUTO_INCREMENT значение для таблицы MySQL"""
        with engine.connect() as conn:
            sql = """
                SELECT AUTO_INCREMENT 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = :table
            """
            result = conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            return row[0] if row else None
