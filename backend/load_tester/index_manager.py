"""
Менеджер создания и удаления индексов для сценариев нагрузочного тестирования
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text


@dataclass
class IndexOperationDetail:
    """Информация об одной операции над индексом"""
    name: str
    table: str
    columns: str
    index_type: str
    creation_time_ms: float = 0.0
    drop_time_ms: float = 0.0
    success: bool = True
    skipped: bool = False
    note: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "table": self.table,
            "columns": self.columns,
            "index_type": self.index_type,
            "creation_time_ms": self.creation_time_ms,
            "drop_time_ms": self.drop_time_ms,
            "success": self.success,
            "skipped": self.skipped,
            "note": self.note,
            "error": self.error,
        }


@dataclass
class IndexOperationResult:
    """Результат пакета операций над индексами"""
    success: bool
    total_time_ms: float
    details: List[IndexOperationDetail] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_time_ms": self.total_time_ms,
            "details": [detail.to_dict() for detail in self.details],
            "errors": self.errors,
        }


class IndexManager:
    """Создание и удаление индексов для сценариев"""

    def _quote_identifier(self, db_type: str, identifier: str) -> str:
        quote = '"' if db_type == "postgresql" else "`"
        sanitized = identifier.strip().replace(quote, "")
        return f"{quote}{sanitized}{quote}"

    def _normalize_columns(self, column_names: str) -> List[str]:
        return [column.strip() for column in column_names.split(",") if column.strip()]

    def _generate_index_name(self, table_name: str, column_names: str) -> str:
        suffix = "_".join(self._normalize_columns(column_names)) or "idx"
        return f"idx_loadtest_{table_name}_{suffix}"[:255]

    def _resolve_index_name(self, index_def: Dict[str, Any]) -> str:
        return index_def.get("index_name") or self._generate_index_name(
            index_def["table_name"],
            index_def["column_names"],
        )

    def _build_column_sql(self, db_type: str, column_names: str) -> str:
        columns = self._normalize_columns(column_names)
        return ", ".join(self._quote_identifier(db_type, column) for column in columns)

    def _build_create_index_sql(self, db_type: str, index_def: Dict[str, Any]) -> str:
        index_name = self._quote_identifier(db_type, self._resolve_index_name(index_def))
        table_name = self._quote_identifier(db_type, index_def["table_name"])
        columns_sql = self._build_column_sql(db_type, index_def["column_names"])
        index_type = (index_def.get("index_type") or "btree").upper()
        is_unique = "UNIQUE " if index_def.get("is_unique") else ""
        condition = (index_def.get("condition") or "").strip()

        if db_type == "postgresql":
            sql = f"CREATE {is_unique}INDEX {index_name} ON {table_name} USING {index_type} ({columns_sql})"
            if condition:
                sql += f" WHERE {condition}"
            return sql

        sql = f"CREATE {is_unique}INDEX {index_name} ON {table_name} ({columns_sql})"
        if index_type and index_type != "BTREE":
            sql += f" USING {index_type}"
        return sql

    def _build_drop_index_sql(self, db_type: str, index_def: Dict[str, Any]) -> str:
        index_name = self._quote_identifier(db_type, self._resolve_index_name(index_def))
        if db_type == "postgresql":
            return f"DROP INDEX IF EXISTS {index_name}"

        table_name = self._quote_identifier(db_type, index_def["table_name"])
        return f"DROP INDEX {index_name} ON {table_name}"

    def _normalize_columns_key(self, column_names: str) -> str:
        return ",".join(column.strip().lower() for column in self._normalize_columns(column_names))

    async def _get_existing_index_names_by_columns(
        self,
        engine,
        db_type: str,
        table_name: str,
    ) -> Dict[str, str]:
        """Получить существующие индексы таблицы как map normalized_columns -> index_name"""
        async with engine.connect() as conn:
            if db_type == "postgresql":
                result = await conn.execute(text("""
                    SELECT
                        i.relname AS index_name,
                        string_agg(a.attname, ',' ORDER BY x.ordinality) AS columns
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, ordinality) ON true
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
                    WHERE t.relname = :table_name
                    GROUP BY i.relname
                """), {"table_name": table_name})
            else:
                result = await conn.execute(text("""
                    SELECT
                        INDEX_NAME AS index_name,
                        GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') AS columns
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :table_name
                    GROUP BY INDEX_NAME
                """), {"table_name": table_name})

            return {
                self._normalize_columns_key(row[1] or ""): row[0]
                for row in result.fetchall()
                if row[1]
            }

    async def create_indexes(
        self,
        engine,
        db_type: str,
        indexes: List[Dict[str, Any]],
        callback=None,
    ) -> IndexOperationResult:
        """Создать все индексы сценария"""
        start_time = time.perf_counter()
        details: List[IndexOperationDetail] = []
        errors: List[str] = []

        for idx, index_def in enumerate(indexes, start=1):
            detail = IndexOperationDetail(
                name=self._resolve_index_name(index_def),
                table=index_def["table_name"],
                columns=index_def["column_names"],
                index_type=index_def.get("index_type", "btree"),
            )
            op_start = time.perf_counter()

            try:
                existing_indexes = await self._get_existing_index_names_by_columns(
                    engine=engine,
                    db_type=db_type,
                    table_name=index_def["table_name"],
                )
                normalized_columns = self._normalize_columns_key(index_def["column_names"])
                existing_index_name = existing_indexes.get(normalized_columns)
                if existing_index_name:
                    detail.name = existing_index_name
                    detail.skipped = True
                    detail.note = "Эквивалентный индекс уже существует"
                    details.append(detail)
                    if callback:
                        await callback(
                            "index_creation_progress",
                            {
                                "current": idx,
                                "total": len(indexes),
                                "index": detail.to_dict(),
                            },
                        )
                    continue

                sql = self._build_create_index_sql(db_type, index_def)
                async with engine.connect() as conn:
                    await conn.execute(text(sql))
                    await conn.commit()
                detail.creation_time_ms = (time.perf_counter() - op_start) * 1000
            except Exception as e:
                detail.success = False
                detail.error = str(e)
                errors.append(f"{detail.name}: {e}")

            details.append(detail)

            if callback:
                await callback(
                    "index_creation_progress",
                    {
                        "current": idx,
                        "total": len(indexes),
                        "index": detail.to_dict(),
                    },
                )

        total_time_ms = (time.perf_counter() - start_time) * 1000
        return IndexOperationResult(
            success=len(errors) == 0,
            total_time_ms=total_time_ms,
            details=details,
            errors=errors,
        )

    async def drop_indexes(
        self,
        engine,
        db_type: str,
        indexes: List[Dict[str, Any]],
        callback=None,
    ) -> IndexOperationResult:
        """Удалить индексы сценария"""
        start_time = time.perf_counter()
        details: List[IndexOperationDetail] = []
        errors: List[str] = []

        for idx, index_def in enumerate(indexes, start=1):
            detail = IndexOperationDetail(
                name=self._resolve_index_name(index_def),
                table=index_def["table_name"],
                columns=index_def["column_names"],
                index_type=index_def.get("index_type", "btree"),
            )
            op_start = time.perf_counter()

            try:
                sql = self._build_drop_index_sql(db_type, index_def)
                async with engine.connect() as conn:
                    await conn.execute(text(sql))
                    await conn.commit()
                detail.drop_time_ms = (time.perf_counter() - op_start) * 1000
            except Exception as e:
                detail.success = False
                detail.error = str(e)
                errors.append(f"{detail.name}: {e}")

            details.append(detail)

            if callback:
                await callback(
                    "index_drop_progress",
                    {
                        "current": idx,
                        "total": len(indexes),
                        "index": detail.to_dict(),
                    },
                )

        total_time_ms = (time.perf_counter() - start_time) * 1000
        return IndexOperationResult(
            success=len(errors) == 0,
            total_time_ms=total_time_ms,
            details=details,
            errors=errors,
        )
