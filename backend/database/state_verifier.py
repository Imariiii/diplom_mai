"""
Верификатор состояния базы данных
Проверяет целостность восстановления данных
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from backend.core.config import RestoreRuntimeConfig, settings
from backend.database.dialects import get_dialect
from backend.database.sql_utils import get_row_count, resolve_dbms_type


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
                         expected_checksum: Optional[str] = None, actual_checksum: Optional[str] = None):
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
    
    def __init__(self, config: Optional[RestoreRuntimeConfig] = None):
        self.config = config or RestoreRuntimeConfig.from_settings(settings)
        self.verify_checksums = self.config.verify_checksums
        self.checksum_max_rows = self.config.checksum_max_rows
    
    async def capture_fingerprint(self, engine: AsyncEngine, tables: Set[str]) -> StateFingerprint:
        """
        Создать "фингерпринт" текущего состояния БД
        
        Args:
            engine: SQLAlchemy async engine
            tables: Множество имён таблиц
            
        Returns:
            StateFingerprint с информацией о состоянии
        """
        fingerprint = StateFingerprint(timestamp=datetime.utcnow())
        dbms_type = resolve_dbms_type(engine)
        
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
    
    async def _capture_table_fingerprint(self, engine: AsyncEngine, table: str, 
                                          dbms_type: str) -> TableFingerprint:
        """Создать фингерпринт отдельной таблицы"""
        
        # Получаем количество строк
        row_count = await get_row_count(engine, table, dbms_type)
        
        # Вычисляем чексумму (только для маленьких таблиц)
        checksum = None
        if self.verify_checksums and row_count <= self.checksum_max_rows:
            checksum = await self._compute_checksum(engine, table, dbms_type)
        
        # Получаем sequence/auto_increment значения
        sequence_value = None
        auto_increment_value = None
        
        async with engine.connect() as conn:
            auto_value = await get_dialect(dbms_type).get_auto_value(conn, table)
        if dbms_type == 'postgresql':
            sequence_value = auto_value
        else:
            auto_increment_value = auto_value
        
        return TableFingerprint(
            table_name=table,
            row_count=row_count,
            checksum=checksum,
            sequence_value=sequence_value,
            auto_increment_value=auto_increment_value
        )
    
    async def _compute_checksum(self, engine: AsyncEngine, table: str, dbms_type: str) -> str:
        """Вычислить чексумму данных таблицы"""
        dialect = get_dialect(dbms_type)
        async with engine.connect() as conn:
            try:
                result = await conn.execute(text(dialect.get_checksum_sql(table)))
                row = result.fetchone()
                return dialect.extract_checksum_value(row)
            except Exception:
                return ""

        return ""