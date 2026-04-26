"""
Модуль анализа схемы подключённой БД для автогенерации сценариев.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

from backend.database.connection import DatabaseConnection
from backend.database.dialects import get_dialect


TYPE_CATEGORY_MAPPING: Dict[str, str] = {
    "smallint": "integer",
    "smallint unsigned": "integer",
    "integer": "integer",
    "integer unsigned": "integer",
    "bigint": "integer",
    "bigint unsigned": "integer",
    "int": "integer",
    "int unsigned": "integer",
    "tinyint": "integer",
    "tinyint unsigned": "integer",
    "mediumint": "integer",
    "mediumint unsigned": "integer",
    "int2": "integer",
    "int4": "integer",
    "int8": "integer",
    "serial": "integer",
    "bigserial": "integer",
    "decimal": "numeric",
    "numeric": "numeric",
    "float": "numeric",
    "float4": "numeric",
    "float8": "numeric",
    "double": "numeric",
    "double precision": "numeric",
    "real": "numeric",
    "money": "numeric",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "datetime": "date",
    "timestamp": "date",
    "timestamp without time zone": "date",
    "timestamp with time zone": "date",
    "time": "date",
    "char": "string",
    "nchar": "string",
    "varchar": "string",
    "nvarchar": "string",
    "character varying": "string",
    "character": "string",
    "text": "string",
    "tinytext": "string",
    "mediumtext": "string",
    "longtext": "string",
    "uuid": "string",
    "json": "string",
    "jsonb": "string",
    "enum": "string",
    "set": "string",
}


@dataclass
class ColumnInfo:
    """Информация о колонке таблицы."""

    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    is_unique: bool = False
    is_partition_key: bool = False
    is_auto_generated: bool = False
    column_default: Optional[str] = None
    has_server_default: bool = False
    default_kind: Optional[str] = None
    identity_generation: Optional[str] = None
    category: str = "other"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "is_nullable": self.is_nullable,
            "is_primary_key": self.is_primary_key,
            "is_unique": self.is_unique,
            "is_partition_key": self.is_partition_key,
            "is_auto_generated": self.is_auto_generated,
            "column_default": self.column_default,
            "has_server_default": self.has_server_default,
            "default_kind": self.default_kind,
            "identity_generation": self.identity_generation,
            "category": self.category,
        }


@dataclass
class ForeignKeyInfo:
    """Информация о foreign key."""

    constraint_name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_name": self.constraint_name,
            "from_table": self.from_table,
            "from_column": self.from_column,
            "to_table": self.to_table,
            "to_column": self.to_column,
        }


@dataclass
class TableInfo:
    """Информация о таблице."""

    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    row_count: int = 0
    foreign_keys_out: List[ForeignKeyInfo] = field(default_factory=list)
    foreign_keys_in: List[ForeignKeyInfo] = field(default_factory=list)
    unique_columns: Set[str] = field(default_factory=set)
    unique_constraints: List[List[str]] = field(default_factory=list)
    check_constraints: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)

    def get_column(self, column_name: str) -> Optional[ColumnInfo]:
        for column in self.columns:
            if column.name == column_name:
                return column
        return None

    def get_columns_by_category(self, category: str) -> List[ColumnInfo]:
        return [column for column in self.columns if column.category == category]

    def has_single_primary_key(self) -> bool:
        return len(self.primary_key) == 1

    def primary_key_column(self) -> Optional[ColumnInfo]:
        if not self.has_single_primary_key():
            return None
        return self.get_column(self.primary_key[0])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "columns": [column.to_dict() for column in self.columns],
            "primary_key": list(self.primary_key),
            "row_count": self.row_count,
            "foreign_keys_out": [fk.to_dict() for fk in self.foreign_keys_out],
            "foreign_keys_in": [fk.to_dict() for fk in self.foreign_keys_in],
            "unique_columns": sorted(self.unique_columns),
            "unique_constraints": [list(columns) for columns in self.unique_constraints],
            "check_constraints": list(self.check_constraints),
            "capabilities": list(self.capabilities),
        }


@dataclass
class SchemaMetadata:
    """Полная метаинформация о схеме БД."""

    connection_id: str
    connection_name: str
    dbms_type: str
    tables: Dict[str, TableInfo]

    def to_dict(self) -> Dict[str, Any]:
        sorted_tables = sorted(self.tables.values(), key=lambda table: table.name)
        return {
            "connection_id": self.connection_id,
            "connection_name": self.connection_name,
            "dbms_type": self.dbms_type,
            "total_tables": len(sorted_tables),
            "tables": [table.to_dict() for table in sorted_tables],
        }


class SchemaAnalyzer:
    """Анализатор схемы подключённой БД."""

    def __init__(self, connection_repo=None):
        self.db_connection = DatabaseConnection()
        if connection_repo:
            self.db_connection.set_connection_repository(connection_repo)

    async def analyze_connection(self, connection_id: str) -> SchemaMetadata:
        """Собрать метаданные схемы для указанного подключения."""
        connection_config = await self.db_connection.ensure_connection_config(connection_id)
        dbms_type = connection_config["dbms_type"]
        dialect = get_dialect(dbms_type)
        engine = await self.db_connection.get_engine_async(connection_id)

        async with engine.connect() as conn:
            tables_result = await conn.execute(text(dialect.get_list_tables_sql()))
            table_names = [row[0] for row in tables_result.fetchall()]

            tables: Dict[str, TableInfo] = {
                table_name: TableInfo(name=table_name)
                for table_name in table_names
            }

            columns_result = await conn.execute(text(dialect.get_columns_sql()))
            for row in columns_result.fetchall():
                (
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    _,
                    identity_generation,
                    default_kind,
                    has_server_default,
                ) = self._normalize_column_row(row)
                if table_name not in tables:
                    continue
                tables[table_name].columns.append(
                    ColumnInfo(
                        name=column_name,
                        data_type=data_type,
                        is_nullable=str(is_nullable).upper() == "YES",
                        column_default=column_default,
                        has_server_default=has_server_default,
                        default_kind=default_kind,
                        identity_generation=identity_generation,
                        is_auto_generated=self._is_auto_generated(
                            column_default=column_default,
                            default_kind=default_kind,
                            identity_generation=identity_generation,
                        ),
                        category=self._categorize_data_type(data_type),
                    )
                )

            primary_keys_result = await conn.execute(text(dialect.get_primary_keys_sql()))
            for row in primary_keys_result.fetchall():
                table_name, column_name, _ = row
                table = tables.get(table_name)
                if not table:
                    continue
                table.primary_key.append(column_name)
                column = table.get_column(column_name)
                if column:
                    column.is_primary_key = True

            unique_constraints_result = await conn.execute(text(dialect.get_unique_constraints_sql()))
            unique_groups: Dict[tuple, List[tuple]] = {}
            for row in unique_constraints_result.fetchall():
                table_name, column_name, constraint_name = row
                table = tables.get(table_name)
                if not table:
                    continue
                unique_groups.setdefault((table_name, constraint_name), []).append((column_name, len(unique_groups)))
            for (table_name, _), column_entries in unique_groups.items():
                table = tables.get(table_name)
                if not table:
                    continue
                columns = [column_name for column_name, _ in column_entries]
                table.unique_constraints.append(columns)
                if len(columns) == 1:
                    column_name = columns[0]
                    table.unique_columns.add(column_name)
                    column = table.get_column(column_name)
                    if column:
                        column.is_unique = True

            check_sql = dialect.get_check_constraints_sql()
            if check_sql:
                try:
                    check_constraints_result = await conn.execute(text(check_sql))
                    for row in check_constraints_result.fetchall():
                        table_name, check_clause = row
                        table = tables.get(table_name)
                        if table and check_clause:
                            table.check_constraints.append(str(check_clause))
                except Exception as exc:
                    print(f"[SCHEMA_ANALYZER] Не удалось получить check constraints: {exc}")

            partition_sql = dialect.get_partition_columns_sql()
            if partition_sql:
                try:
                    partition_columns_result = await conn.execute(text(partition_sql))
                    for row in partition_columns_result.fetchall():
                        table_name, column_name = row
                        table = tables.get(table_name)
                        if not table:
                            continue
                        column = table.get_column(column_name)
                        if column:
                            column.is_partition_key = True
                except Exception as exc:
                    print(f"[SCHEMA_ANALYZER] Не удалось получить partition columns: {exc}")

            foreign_keys_result = await conn.execute(text(dialect.get_foreign_keys_detailed_sql()))
            for row in foreign_keys_result.fetchall():
                constraint_name, from_table, from_column, to_table, to_column = row
                if from_table not in tables or to_table not in tables:
                    continue
                foreign_key = ForeignKeyInfo(
                    constraint_name=constraint_name,
                    from_table=from_table,
                    from_column=from_column,
                    to_table=to_table,
                    to_column=to_column,
                )
                tables[from_table].foreign_keys_out.append(foreign_key)
                tables[to_table].foreign_keys_in.append(foreign_key)

            for table_name, table in tables.items():
                self._infer_primary_key_heuristic(table)

            for table_name, table in tables.items():
                try:
                    row_count_result = await conn.execute(text(dialect.get_row_count_sql(table_name)))
                    row = row_count_result.fetchone()
                    table.row_count = int(row[0] or 0) if row else 0
                except Exception as exc:
                    print(f"[SCHEMA_ANALYZER] Не удалось получить row_count для {table_name}: {exc}")
                    table.row_count = 0
                table.capabilities = self._classify_table(table, tables)

        return SchemaMetadata(
            connection_id=connection_id,
            connection_name=connection_config.get("name", connection_id),
            dbms_type=dbms_type,
            tables=tables,
        )

    @staticmethod
    def _infer_primary_key_heuristic(table: TableInfo) -> None:
        """Определить вероятный PK эвристически, если constraints не загрузились."""
        if table.primary_key:
            return
        candidates = [
            col for col in table.columns
            if col.is_auto_generated
            and col.category in {"integer", "numeric"}
            and not col.is_nullable
        ]
        if len(candidates) == 1:
            pk_col = candidates[0]
            table.primary_key.append(pk_col.name)
            pk_col.is_primary_key = True

    def _categorize_data_type(self, data_type: Optional[str]) -> str:
        """Нормализовать тип данных до одной из прикладных категорий."""
        normalized = (data_type or "").strip().lower()
        return TYPE_CATEGORY_MAPPING.get(normalized, "other")

    @staticmethod
    def _normalize_column_row(row) -> tuple:
        """Привести результат dialect.get_columns_sql к расширенному формату."""
        values = tuple(row)
        table_name, column_name, data_type, is_nullable, column_default, ordinal_position = values[:6]
        identity_generation = values[6] if len(values) > 6 else None
        default_kind = values[7] if len(values) > 7 else None
        has_server_default_raw = values[8] if len(values) > 8 else column_default is not None
        has_server_default = str(has_server_default_raw).lower() in {"true", "t", "1", "yes"}
        return (
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default,
            ordinal_position,
            identity_generation,
            default_kind,
            has_server_default,
        )

    def _is_auto_generated(
        self,
        column_default: Optional[str],
        default_kind: Optional[str] = None,
        identity_generation: Optional[str] = None,
    ) -> bool:
        """Определить, генерируется ли значение колонки СУБД автоматически."""
        default = (column_default or "").lower()
        kind = (default_kind or "").lower()
        identity = (identity_generation or "").lower()
        return (
            "nextval(" in default
            or "auto_increment" in default
            or "identity" in default
            or kind in {"identity", "serial", "auto_increment", "generated"}
            or bool(identity)
        )

    def _classify_table(self, table: TableInfo, all_tables: Optional[Dict[str, "TableInfo"]] = None) -> List[str]:
        """Определить прикладные роли таблицы для шаблонов запросов."""
        capabilities: List[str] = []
        primary_key_column = table.primary_key_column()
        non_pk_columns = [column for column in table.columns if not column.is_primary_key]
        foreign_key_columns = set(fk.from_column for fk in table.foreign_keys_out)
        mutable_columns = [
            column for column in non_pk_columns
            if column.name not in foreign_key_columns
            and not column.is_unique
            and not column.is_partition_key
            and column.category in {"string", "numeric", "date", "boolean"}
        ]

        if primary_key_column and table.row_count >= 10:
            capabilities.append("readable")

        if table.foreign_keys_out or table.foreign_keys_in:
            capabilities.append("joinable")

        if table.row_count >= 100 and (
            table.get_columns_by_category("numeric") or
            table.get_columns_by_category("integer") or
            table.foreign_keys_out or table.foreign_keys_in
        ):
            capabilities.append("aggregatable")

        if (
            table.get_columns_by_category("date") or
            table.get_columns_by_category("numeric") or
            table.get_columns_by_category("integer")
        ):
            capabilities.append("range_scannable")

        if primary_key_column and mutable_columns:
            capabilities.append("updatable")

        if self._is_insert_safe(table):
            capabilities.append("insert_safe")

        has_fk_in = bool(table.foreign_keys_in)
        heuristic_fk_in = False
        if not has_fk_in and all_tables:
            expected_fk_col = f"{table.name}_id"
            for other_name, other_table in all_tables.items():
                if other_name == table.name:
                    continue
                for col in other_table.columns:
                    if col.name == expected_fk_col and col.category in {"integer", "numeric"}:
                        heuristic_fk_in = True
                        break
                if heuristic_fk_in:
                    break

        if primary_key_column and not has_fk_in and not heuristic_fk_in and table.row_count > 0:
            capabilities.append("delete_safe")

        return capabilities

    def _is_insert_safe(self, table: TableInfo) -> bool:
        """Проверить, можно ли с высокой вероятностью безопасно собрать INSERT."""
        if not table.columns:
            return False

        required_columns = [
            column for column in table.columns
            if not column.is_primary_key and not column.is_nullable and not column.column_default
        ]
        if not required_columns:
            return True

        foreign_key_columns = set(fk.from_column for fk in table.foreign_keys_out)
        supported_categories = {"integer", "numeric", "string", "date", "boolean"}
        for column in required_columns:
            if column.name in foreign_key_columns:
                continue
            if column.category not in supported_categories:
                return False

        for unique_constraint in table.unique_constraints:
            if len(unique_constraint) <= 1:
                continue
            constrained_columns = [
                table.get_column(column_name)
                for column_name in unique_constraint
            ]
            if all(column is not None for column in constrained_columns):
                # Независимая выборка существующих значений по composite UNIQUE легко
                # создаёт уже существующую комбинацию. Без доменной стратегии такие
                # таблицы небезопасны для универсального INSERT.
                return False
        return True
