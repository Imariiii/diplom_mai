"""
Preflight-проверка SQL bundle перед запуском нагрузочного теста.
"""
import re
from typing import Any, Dict, List, Set

from sqlalchemy import text

from backend.database.dialects import get_dialect
from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.schema_analyzer import SchemaAnalyzer, SchemaMetadata


class ScenarioBundleValidator:
    """Проверяет, что bundle исполним на выбранных подключениях."""

    def __init__(self, connection_repository: ConnectionRepository):
        self.connection_repository = connection_repository
        self.schema_analyzer = SchemaAnalyzer(connection_repo=connection_repository)

    async def validate_bundle_for_connections(
        self,
        bundle: Dict[str, Any],
        connection_ids: List[str],
    ) -> Dict[str, Any]:
        """Проверить bundle на всех целевых БД."""
        connections = await self.connection_repository.bulk_get_connections(connection_ids)
        errors: List[str] = []
        warnings: List[str] = []
        checked_connections: List[Dict[str, Any]] = []

        for connection in connections:
            metadata = await self.schema_analyzer.analyze_connection(str(connection.id))
            connection_errors, connection_warnings = await self._validate_for_connection(
                bundle=bundle,
                connection_id=str(connection.id),
                connection_name=connection.name,
                dbms_type=connection.dbms_type,
                metadata=metadata,
            )
            errors.extend(connection_errors)
            warnings.extend(connection_warnings)
            checked_connections.append({
                "id": str(connection.id),
                "name": connection.name,
                "dbms_type": connection.dbms_type,
            })

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "checked_connections": checked_connections,
        }

    async def _validate_for_connection(
        self,
        bundle: Dict[str, Any],
        connection_id: str,
        connection_name: str,
        dbms_type: str,
        metadata: SchemaMetadata,
    ) -> tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        tables = metadata.tables

        for query in bundle.get("queries", []):
            sql_template = query.get("sql_template") or ""
            query_label = query.get("description") or sql_template[:80]
            referenced_tables = self._extract_table_names(sql_template)
            for table_name in referenced_tables:
                if table_name not in tables:
                    errors.append(f"{connection_name}: запрос '{query_label}' ссылается на отсутствующую таблицу {table_name}")

            for param in query.get("params", []):
                table_ref = param.get("table_ref")
                column_ref = param.get("column_ref")
                if param.get("param_type") != "random_from_table":
                    continue
                if not table_ref or not column_ref:
                    errors.append(f"{connection_name}: параметр {param.get('param_name')} не содержит table_ref/column_ref")
                    continue
                table = tables.get(table_ref)
                if not table:
                    errors.append(f"{connection_name}: параметр {param.get('param_name')} ссылается на отсутствующую таблицу {table_ref}")
                    continue
                column = table.get_column(column_ref)
                if not column:
                    errors.append(f"{connection_name}: параметр {param.get('param_name')} ссылается на отсутствующую колонку {table_ref}.{column_ref}")
                    continue
                try:
                    has_sample = await self._has_sample_value(connection_id, dbms_type, table_ref, column_ref)
                except Exception as exc:
                    errors.append(
                        f"{connection_name}: не удалось проверить значения параметра "
                        f"{table_ref}.{column_ref}: {exc}"
                    )
                    continue
                if not has_sample:
                    errors.append(f"{connection_name}: нет значений для параметра {table_ref}.{column_ref}")

            if query.get("query_type") in {"update", "insert"}:
                self._validate_write_query(sql_template, metadata, connection_name, errors, warnings)

        for index_def in bundle.get("indexes", []):
            table = tables.get(index_def.get("table_name"))
            if not table:
                warnings.append(f"{connection_name}: индекс bundle ссылается на отсутствующую таблицу {index_def.get('table_name')}")
                continue
            for column_name in self._split_columns(index_def.get("column_names") or ""):
                if not table.get_column(column_name):
                    warnings.append(f"{connection_name}: индекс bundle ссылается на отсутствующую колонку {table.name}.{column_name}")

        return errors, warnings

    async def _has_sample_value(self, connection_id: str, dbms_type: str, table_name: str, column_name: str) -> bool:
        dialect = get_dialect(dbms_type)
        engine = await self.schema_analyzer.db_connection.get_engine_async(connection_id)
        sql = dialect.get_sample_column_values_sql(table_name, column_name)
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), {"limit": 1})
            return result.fetchone() is not None

    def _validate_write_query(
        self,
        sql_template: str,
        metadata: SchemaMetadata,
        connection_name: str,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        update_match = re.search(r"\bUPDATE\s+([A-Za-z_][\w]*)\s+SET\s+([A-Za-z_][\w]*)", sql_template, re.IGNORECASE)
        if update_match:
            table_name, column_name = update_match.groups()
            table = metadata.tables.get(table_name)
            column = table.get_column(column_name) if table else None
            if column and column.is_partition_key:
                errors.append(f"{connection_name}: UPDATE меняет partition key {table_name}.{column_name}")
            if column and (column.is_primary_key or column.is_unique):
                errors.append(f"{connection_name}: UPDATE меняет ключевую колонку {table_name}.{column_name}")

    def _extract_table_names(self, sql_template: str) -> Set[str]:
        names: Set[str] = set()
        pattern = re.compile(
            r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][\w]*)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(sql_template):
            names.add(match.group(1))
        return names

    def _split_columns(self, column_names: str) -> List[str]:
        return [column.strip() for column in column_names.split(",") if column.strip()]
