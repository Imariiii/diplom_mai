"""
Preflight-проверка SQL bundle перед запуском нагрузочного теста.
"""
import re
from typing import Any, Dict, List, Optional, Set

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
        smoke_run: bool = False,
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
                smoke_run=smoke_run,
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
        smoke_run: bool = False,
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
                if smoke_run and not errors:
                    try:
                        await self._smoke_run_write_query(connection_id, dbms_type, query)
                    except Exception as exc:
                        errors.append(
                            f"{connection_name}: smoke-run запроса '{query_label}' завершился ошибкой: {exc}"
                        )

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

        insert_match = re.search(
            r"\bINSERT\s+INTO\s+([A-Za-z_][\w]*)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)",
            sql_template,
            re.IGNORECASE | re.DOTALL,
        )
        if insert_match:
            table_name, columns_sql, values_sql = insert_match.groups()
            table = metadata.tables.get(table_name)
            if not table:
                return
            insert_columns = self._split_columns(columns_sql)
            insert_column_set = set(insert_columns)
            insert_values = self._split_sql_list(values_sql)

            if len(insert_values) != len(insert_columns):
                errors.append(f"{connection_name}: INSERT в {table_name} имеет разное число колонок и значений")
                return

            for column in table.columns:
                if column.name not in insert_column_set:
                    if not column.is_nullable and not self._has_insert_default(column):
                        errors.append(
                            f"{connection_name}: INSERT в {table_name} пропускает обязательную колонку "
                            f"{column.name} без server default"
                        )
                    continue

                value_sql = insert_values[insert_columns.index(column.name)].strip()
                if column.is_auto_generated and value_sql.upper() != "DEFAULT":
                    errors.append(
                        f"{connection_name}: INSERT в {table_name} явно заполняет auto-generated колонку "
                        f"{column.name}"
                    )

            for unique_columns in table.unique_constraints:
                if len(unique_columns) > 1 and set(unique_columns).issubset(insert_column_set):
                    errors.append(
                        f"{connection_name}: INSERT в {table_name} заполняет composite UNIQUE "
                        f"({', '.join(unique_columns)}), что небезопасно для универсальной генерации"
                    )

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

    def _split_sql_list(self, sql_list: str) -> List[str]:
        """Разбить SQL-список по запятым без захода внутрь кавычек/скобок."""
        parts: List[str] = []
        current: List[str] = []
        quote: Optional[str] = None
        depth = 0
        for char in sql_list:
            if quote:
                current.append(char)
                if char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                current.append(char)
                continue
            if char == "(":
                depth += 1
                current.append(char)
                continue
            if char == ")":
                depth = max(0, depth - 1)
                current.append(char)
                continue
            if char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current:
            parts.append("".join(current).strip())
        return parts

    def _has_insert_default(self, column) -> bool:
        default_kind = (getattr(column, "default_kind", None) or "").lower()
        default_text = (column.column_default or "").strip().lower()
        return bool(
            getattr(column, "has_server_default", False)
            or column.column_default
            or getattr(column, "identity_generation", None)
            or default_kind in {"identity", "serial", "auto_increment", "generated", "default"}
            or default_text in {"identity", "auto_increment"}
            or "nextval(" in default_text
        )

    async def _smoke_run_write_query(self, connection_id: str, dbms_type: str, query: Dict[str, Any]) -> None:
        """Выполнить write-запрос в транзакции и откатить результат."""
        dialect = get_dialect(dbms_type)
        engine = await self.schema_analyzer.db_connection.get_engine_async(connection_id)
        params: Dict[str, Any] = {}
        for param in query.get("params", []):
            if param.get("param_type") != "random_from_table":
                continue
            table_ref = param.get("table_ref")
            column_ref = param.get("column_ref")
            if not table_ref or not column_ref:
                continue
            sql = dialect.get_sample_column_values_sql(table_ref, column_ref)
            async with engine.connect() as conn:
                result = await conn.execute(text(sql), {"limit": 1})
                row = result.fetchone()
                if row is None:
                    raise ValueError(f"Нет значения для {table_ref}.{column_ref}")
                params[param["param_name"]] = row[0]

        executable_sql = query.get("sql_template") or ""
        for param_name in sorted(params.keys(), key=len, reverse=True):
            executable_sql = executable_sql.replace("'{" + param_name + "}'", f":{param_name}")
            executable_sql = executable_sql.replace("{" + param_name + "}", f":{param_name}")
        missing = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", executable_sql)
        if missing:
            raise KeyError(", ".join(sorted(set(missing))))

        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text(executable_sql), params)
            finally:
                await transaction.rollback()
