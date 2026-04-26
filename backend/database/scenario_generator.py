"""
Модуль автоматической генерации сценариев тестирования по схеме БД.
"""
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.database.query_templates import QUERY_TEMPLATES, QueryTemplateDefinition, TemplateRequirements
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.schema_analyzer import ColumnInfo, SchemaAnalyzer, SchemaMetadata, TableInfo


DEFAULT_SCENARIO_TYPES: List[str] = [
    "read_only",
    "write_only",
    "mixed_light",
    "mixed_heavy",
    "oltp",
    "olap",
]

SCENARIO_GENERATOR_VERSION = "logical-scenario-generator-v5"

SCENARIO_QUERY_LIMITS: Dict[str, int] = {
    "read_only": 6,
    "write_only": 4,
    "mixed_light": 5,
    "mixed_heavy": 6,
    "oltp": 5,
    "olap": 5,
}


class ScenarioGenerator:
    """Генератор сценариев тестирования на базе метаданных схемы."""

    def __init__(self, connection_repo=None, bundle_repository: Optional[ScenarioBundleRepository] = None):
        self.connection_repo = connection_repo
        self.bundle_repository = bundle_repository
        self.schema_analyzer = SchemaAnalyzer(connection_repo=connection_repo)

    async def build_generation_preview(self, connection_id: str) -> Dict[str, Any]:
        """Построить preview без сохранения сценариев."""
        metadata = await self.schema_analyzer.analyze_connection(connection_id)
        preview = metadata.to_dict()
        preview["available_scenario_types"] = self._get_available_scenario_types(metadata)
        preview["matching_templates"] = self._collect_matching_templates(metadata)
        return preview

    async def build_query_sets_for_connection(
        self,
        connection_id: str,
        scenario_types: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Собрать SQL-наборы по logical scenario без сохранения в БД."""
        metadata = await self.schema_analyzer.analyze_connection(connection_id)
        selected_types = self._normalize_scenario_types(scenario_types)
        query_sets: Dict[str, List[Dict[str, Any]]] = {}
        for scenario_type in selected_types:
            queries, _ = self._build_scenario_assets(metadata, scenario_type)
            if queries:
                query_sets[scenario_type] = queries
        return query_sets

    async def generate_bundles_for_profile(
        self,
        schema_profile_id: str,
        reference_connection_id: str,
        scenario_types: Optional[List[str]] = None,
        generation_source: str = SCENARIO_GENERATOR_VERSION,
    ) -> List[Dict[str, Any]]:
        """Сгенерировать и сохранить канонические bundles профиля."""
        if self.bundle_repository is None:
            raise ValueError("ScenarioBundleRepository не передан в ScenarioGenerator")

        metadata = await self.schema_analyzer.analyze_connection(reference_connection_id)
        selected_types = self._normalize_scenario_types(scenario_types)
        generated_bundles: List[Dict[str, Any]] = []

        for scenario_type in selected_types:
            queries, indexes = self._build_scenario_assets(metadata, scenario_type)
            if not queries:
                continue

            bundle = await self.bundle_repository.upsert_generated_bundle(
                schema_profile_id=schema_profile_id,
                scenario_template_id=scenario_type,
                name=f"{scenario_type}::{metadata.connection_name}::canonical",
                description=(
                    f"Канонический bundle, сгенерированный по эталонной БД "
                    f"'{metadata.connection_name}'"
                ),
                generation_source=generation_source,
                generated_from_connection_id=reference_connection_id,
                queries=queries,
                indexes=indexes,
            )
            full_bundle = await self.bundle_repository.get_bundle(str(bundle.id))
            if full_bundle:
                generated_bundles.append(full_bundle.to_dict())

        return generated_bundles

    def _normalize_scenario_types(self, scenario_types: Optional[List[str]]) -> List[str]:
        """Нормализовать и провалидировать список типов сценариев."""
        requested = scenario_types or DEFAULT_SCENARIO_TYPES
        normalized: List[str] = []
        for scenario_type in requested:
            if scenario_type in DEFAULT_SCENARIO_TYPES and scenario_type not in normalized:
                normalized.append(scenario_type)
        return normalized

    def _get_available_scenario_types(self, metadata: SchemaMetadata) -> List[str]:
        """Определить, для каких типов сценариев можно собрать хотя бы один запрос."""
        available: List[str] = []
        for scenario_type in DEFAULT_SCENARIO_TYPES:
            queries, _ = self._build_scenario_assets(metadata, scenario_type)
            if queries:
                available.append(scenario_type)
        return available

    def _collect_matching_templates(self, metadata: SchemaMetadata) -> Dict[str, List[str]]:
        """Собрать список шаблонов, применимых к каждой таблице."""
        matching: Dict[str, List[str]] = {}
        for table in metadata.tables.values():
            matches: List[str] = []
            for template in QUERY_TEMPLATES:
                if self._table_matches_requirements(table, template.requirements):
                    matches.append(template.id)
            matching[table.name] = matches
        return matching

    def _build_queries_for_scenario(self, metadata: SchemaMetadata, scenario_type: str) -> List[Dict[str, Any]]:
        """Построить набор конкретных SQL-запросов для одного типа сценария."""
        queries, _ = self._build_scenario_assets(metadata, scenario_type)
        return queries

    def _build_scenario_assets(
        self,
        metadata: SchemaMetadata,
        scenario_type: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Построить queries и индексы для logical scenario."""
        max_queries = SCENARIO_QUERY_LIMITS.get(scenario_type, 5)
        queries: List[Dict[str, Any]] = []
        index_hints: List[Dict[str, Any]] = []
        used_templates: Set[str] = set()
        query_types_seen: Set[str] = set()

        is_mixed = "mixed" in scenario_type

        applicable_templates = [
            t for t in QUERY_TEMPLATES
            if scenario_type in t.scenario_types
        ]

        if is_mixed:
            required_types = {"select", "update", "insert"}
            for required_type in required_types:
                for template in applicable_templates:
                    if template.id in used_templates or template.query_type != required_type:
                        continue
                    query = self._build_query_from_template(metadata, template)
                    if not query:
                        continue
                    queries.append(self._strip_private_fields(query))
                    index_hints.extend(deepcopy(query.get("_index_hints", [])))
                    used_templates.add(template.id)
                    query_types_seen.add(template.query_type)
                    break

        for template in applicable_templates:
            if len(queries) >= max_queries:
                break
            if template.id in used_templates:
                continue
            query = self._build_query_from_template(metadata, template)
            if not query:
                continue
            queries.append(self._strip_private_fields(query))
            index_hints.extend(deepcopy(query.get("_index_hints", [])))
            used_templates.add(template.id)
            query_types_seen.add(template.query_type)

        indexes = self._deduplicate_index_hints(
            metadata=metadata,
            scenario_type=scenario_type,
            runtime_hints=index_hints,
        )
        return queries, indexes

    def _build_query_from_template(
        self,
        metadata: SchemaMetadata,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        """Собрать конкретный SQL для указанного шаблона."""
        if template.id == "select_join_chain":
            return self._build_select_join_chain(metadata, template)

        candidate_tables = self._candidate_tables_for_template(metadata, template)
        for table in candidate_tables:
            builder = getattr(self, f"_template_{template.id}", None)
            if not builder:
                return None
            result = builder(metadata, table, template)
            if result:
                return result
        return None

    def _candidate_tables_for_template(
        self,
        metadata: SchemaMetadata,
        template: QueryTemplateDefinition,
    ) -> List[TableInfo]:
        """Подобрать таблицы-кандидаты для шаблона."""
        tables = [
            table
            for table in metadata.tables.values()
            if self._table_matches_requirements(table, template.requirements)
        ]
        return sorted(tables, key=lambda table: (-table.row_count, table.name))

    def _table_matches_requirements(self, table: TableInfo, requirements: TemplateRequirements) -> bool:
        """Проверить применимость шаблона к таблице."""
        if requirements.has_single_pk and not table.has_single_primary_key():
            return False
        if requirements.has_fk_out and not table.foreign_keys_out:
            return False
        if requirements.has_fk_in_or_out and not (table.foreign_keys_out or table.foreign_keys_in):
            return False
        if requirements.has_numeric_column and not (
            table.get_columns_by_category("numeric") or table.get_columns_by_category("integer")
        ):
            return False
        if requirements.has_date_column and not table.get_columns_by_category("date"):
            return False
        if requirements.has_timestamp_column and not self._pick_timestamp_column(table):
            return False
        if requirements.insert_safe and "insert_safe" not in table.capabilities:
            return False
        if requirements.delete_safe and "delete_safe" not in table.capabilities:
            return False
        if table.row_count < requirements.min_rows:
            return False
        return True

    def _template_select_by_pk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        pk_column = table.primary_key_column()
        if not pk_column:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        sql_template = (
            f"SELECT * FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
        )

    def _template_select_projection_by_pk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        pk_column = table.primary_key_column()
        if not pk_column:
            return None
        projection_columns = [
            column for column in table.columns
            if column.name != pk_column.name
        ][:3]
        if not projection_columns:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        projection_sql = ", ".join(
            self._identifier(column.name)
            for column in projection_columns
        )
        sql_template = (
            f"SELECT {projection_sql} FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
        )

    def _template_select_by_fk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        foreign_key = table.foreign_keys_out[0] if table.foreign_keys_out else None
        if not foreign_key:
            return None
        column = table.get_column(foreign_key.from_column)
        if not column:
            return None
        placeholder_name = f"{table.name}_{foreign_key.from_column}"
        sql_template = (
            f"SELECT * FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(foreign_key.from_column)} = "
            f"{self._placeholder(placeholder_name, column.category)} LIMIT 100"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[
                self._random_from_table_param(
                    placeholder_name,
                    foreign_key.to_table,
                    foreign_key.to_column,
                )
            ],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=foreign_key.from_column,
                    description=f"Ускоряет фильтрацию и JOIN по {table.name}.{foreign_key.from_column}",
                )
            ],
        )

    def _template_select_join_fk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        foreign_key = table.foreign_keys_out[0] if table.foreign_keys_out else None
        pk_column = table.primary_key_column()
        if not foreign_key or not pk_column:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        sql_template = (
            f"SELECT a.*, b.* FROM {self._identifier(table.name)} a "
            f"JOIN {self._identifier(foreign_key.to_table)} b "
            f"ON a.{self._identifier(foreign_key.from_column)} = "
            f"b.{self._identifier(foreign_key.to_column)} "
            f"WHERE a.{self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=(
                f"{template.description} Таблицы: {table.name} -> {foreign_key.to_table}"
            ),
            params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=foreign_key.from_column,
                    description=f"Ускоряет JOIN из {table.name} в {foreign_key.to_table}",
                )
            ],
        )

    def _build_select_join_chain(
        self,
        metadata: SchemaMetadata,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        tables = sorted(metadata.tables.values(), key=lambda table: (-table.row_count, table.name))
        for table in tables:
            pk_column = table.primary_key_column()
            if not pk_column:
                continue
            for fk_ab in table.foreign_keys_out:
                middle_table = metadata.tables.get(fk_ab.to_table)
                if not middle_table:
                    continue
                for fk_bc in middle_table.foreign_keys_out:
                    placeholder_name = f"{table.name}_{pk_column.name}"
                    sql_template = (
                        f"SELECT a.*, b.*, c.* FROM {self._identifier(table.name)} a "
                        f"JOIN {self._identifier(middle_table.name)} b "
                        f"ON a.{self._identifier(fk_ab.from_column)} = "
                        f"b.{self._identifier(fk_ab.to_column)} "
                        f"JOIN {self._identifier(fk_bc.to_table)} c "
                        f"ON b.{self._identifier(fk_bc.from_column)} = "
                        f"c.{self._identifier(fk_bc.to_column)} "
                        f"WHERE a.{self._identifier(pk_column.name)} = "
                        f"{self._placeholder(placeholder_name, pk_column.category)}"
                    )
                    return self._build_query_payload(
                        template=template,
                        sql_template=sql_template,
                        description=(
                            f"{template.description} Таблицы: "
                            f"{table.name} -> {middle_table.name} -> {fk_bc.to_table}"
                        ),
                        params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
                        index_hints=[
                            self._build_index_hint(
                                table_name=table.name,
                                column_names=fk_ab.from_column,
                                description=f"Ускоряет первый JOIN из {table.name} в {middle_table.name}",
                            ),
                            self._build_index_hint(
                                table_name=middle_table.name,
                                column_names=fk_bc.from_column,
                                description=f"Ускоряет второй JOIN из {middle_table.name} в {fk_bc.to_table}",
                            ),
                        ],
                    )
        return None

    def _template_aggregation_count_group(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        group_column = self._pick_group_column(table)
        if not group_column:
            return None
        sql_template = (
            f"SELECT {self._identifier(group_column.name)}, COUNT(*) AS item_count "
            f"FROM {self._identifier(table.name)} "
            f"GROUP BY {self._identifier(group_column.name)} "
            f"ORDER BY item_count DESC"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=group_column.name,
                    description=f"Поддерживает GROUP BY по {table.name}.{group_column.name}",
                )
            ],
        )

    def _template_aggregation_sum_numeric(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        group_column = self._pick_group_column(table)
        metric_column = self._pick_metric_column(table)
        if not group_column or not metric_column:
            return None
        sql_template = (
            f"SELECT {self._identifier(group_column.name)}, COUNT(*) AS row_count, "
            f"SUM({self._identifier(metric_column.name)}) AS total_value, "
            f"AVG({self._identifier(metric_column.name)}) AS avg_value "
            f"FROM {self._identifier(table.name)} "
            f"GROUP BY {self._identifier(group_column.name)} "
            f"ORDER BY total_value DESC"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=f"{group_column.name},{metric_column.name}",
                    description=(
                        f"Поддерживает агрегацию по {table.name}.{group_column.name} "
                        f"и вычисления по {metric_column.name}"
                    ),
                )
            ],
        )

    def _template_range_scan_date(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        date_column = self._pick_timestamp_column(table) or self._pick_first_column(table, "date")
        if not date_column:
            return None
        placeholder_name = f"{table.name}_{date_column.name}_from"
        sql_template = (
            f"SELECT * FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(date_column.name)} >= "
            f"{self._placeholder(placeholder_name, date_column.category)} "
            f"ORDER BY {self._identifier(date_column.name)} LIMIT 100"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, date_column.name)],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=date_column.name,
                    description=f"Ускоряет range scan по {table.name}.{date_column.name}",
                )
            ],
        )

    def _template_range_scan_numeric(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        numeric_column = self._pick_metric_column(table)
        if not numeric_column:
            return None
        placeholder_name = f"{table.name}_{numeric_column.name}_min"
        sql_template = (
            f"SELECT * FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(numeric_column.name)} >= "
            f"{self._placeholder(placeholder_name, numeric_column.category)} "
            f"ORDER BY {self._identifier(numeric_column.name)} LIMIT 100"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, numeric_column.name)],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=numeric_column.name,
                    description=f"Ускоряет range scan по {table.name}.{numeric_column.name}",
                )
            ],
        )

    def _template_update_timestamp_by_pk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        pk_column = table.primary_key_column()
        target_column = self._pick_mutable_column(table, {"date"}, metadata)
        if not pk_column or not target_column:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        target_placeholder_name = f"{table.name}_{target_column.name}"
        sql_template = (
            f"UPDATE {self._identifier(table.name)} "
            f"SET {self._identifier(target_column.name)} = "
            f"{self._placeholder(target_placeholder_name, target_column.category)} "
            f"WHERE {self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[
                self._random_from_table_param(placeholder_name, table.name, pk_column.name),
                self._random_from_table_param(target_placeholder_name, table.name, target_column.name),
            ],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=target_column.name,
                    description=(
                        f"Добавляет стоимость поддержки secondary index при обновлении "
                        f"{table.name}.{target_column.name}"
                    ),
                )
            ],
        )

    def _template_update_numeric_by_pk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        pk_column = table.primary_key_column()
        target_column = self._pick_mutable_column(table, {"numeric", "integer"}, metadata)
        if not pk_column or not target_column:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        sql_template = (
            f"UPDATE {self._identifier(table.name)} "
            f"SET {self._identifier(target_column.name)} = "
            f"{self._identifier(target_column.name)} + 1 "
            f"WHERE {self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
            index_hints=[
                self._build_index_hint(
                    table_name=table.name,
                    column_names=target_column.name,
                    description=(
                        f"Добавляет стоимость поддержки secondary index при обновлении "
                        f"{table.name}.{target_column.name}"
                    ),
                )
            ],
        )

    def _template_insert_basic(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        insert_parts: List[Tuple[ColumnInfo, str, Optional[Dict[str, Any]]]] = []
        foreign_key_mapping = {
            fk.from_column: fk
            for fk in table.foreign_keys_out
        }

        self._enrich_fk_mapping_heuristic(metadata, table, foreign_key_mapping)

        for column in table.columns:
            if column.is_auto_generated:
                continue
            if column.is_primary_key and column.column_default:
                continue
            if column.is_partition_key:
                if not column.is_nullable and not column.column_default:
                    return None
                continue
            part = self._build_insert_part(table.name, column, foreign_key_mapping.get(column.name))
            if part is None:
                if not column.is_nullable and not column.column_default:
                    return None
                continue
            insert_parts.append((column, part[0], part[1]))

        if not insert_parts:
            return None

        columns_sql = ", ".join(
            self._identifier(column.name)
            for column, _, _ in insert_parts
        )
        values_sql = ", ".join(value_sql for _, value_sql, _ in insert_parts)
        params = [
            param for _, _, param in insert_parts
            if param is not None
        ]

        sql_template = (
            f"INSERT INTO {self._identifier(table.name)} ({columns_sql}) "
            f"VALUES ({values_sql})"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=params,
        )

    def _template_delete_by_pk(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        template: QueryTemplateDefinition,
    ) -> Optional[Dict[str, Any]]:
        pk_column = table.primary_key_column()
        if not pk_column:
            return None
        placeholder_name = f"{table.name}_{pk_column.name}"
        sql_template = (
            f"DELETE FROM {self._identifier(table.name)} "
            f"WHERE {self._identifier(pk_column.name)} = "
            f"{self._placeholder(placeholder_name, pk_column.category)}"
        )
        return self._build_query_payload(
            template=template,
            sql_template=sql_template,
            description=f"{template.description} Таблица: {table.name}",
            params=[self._random_from_table_param(placeholder_name, table.name, pk_column.name)],
        )

    def _build_insert_part(
        self,
        table_name: str,
        column: ColumnInfo,
        foreign_key,
    ) -> Optional[Tuple[str, Optional[Dict[str, Any]]]]:
        """Построить часть VALUES для INSERT."""
        placeholder_name = f"insert_{column.name}"
        if foreign_key:
            return (
                self._placeholder(placeholder_name, column.category),
                self._random_from_table_param(placeholder_name, foreign_key.to_table, foreign_key.to_column),
            )

        if column.category == "string":
            if column.name.endswith("_id") or column.is_unique:
                return (
                    self._placeholder(placeholder_name, column.category),
                    {"param_name": placeholder_name, "param_type": "uuid"},
                )
            return (
                self._placeholder(placeholder_name, column.category),
                {
                    "param_name": placeholder_name,
                    "param_type": "random_string",
                    "string_length": 16,
                },
            )

        if column.category in {"integer", "numeric"}:
            if column.is_unique:
                return None
            return (
                self._placeholder(placeholder_name, column.category),
                {
                    "param_name": placeholder_name,
                    "param_type": "random_int",
                    "min_value": 1,
                    "max_value": 1000000,
                },
            )

        if column.category == "date":
            return (
                self._placeholder(placeholder_name, column.category),
                self._random_from_table_param(placeholder_name, table_name, column.name),
            )

        if column.category == "boolean":
            return ("TRUE", None)

        if column.column_default or column.is_nullable:
            return None

        return None

    def _strip_private_fields(self, query: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in query.items()
            if not key.startswith("_")
        }

    def _deduplicate_index_hints(
        self,
        metadata: SchemaMetadata,
        scenario_type: str,
        runtime_hints: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Нормализовать индексные подсказки, полученные из шаблонов запросов."""
        deduped: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str]] = set()

        for index_hint in runtime_hints:
            table_name = index_hint["table_name"]
            table = metadata.tables.get(table_name)
            if not table:
                continue
            normalized_columns = ",".join(
                column.strip().lower()
                for column in index_hint["column_names"].split(",")
                if column.strip()
            )
            if not normalized_columns:
                continue
            key = (table_name.lower(), normalized_columns)
            if key in seen:
                continue
            if self._is_redundant_index(table, normalized_columns):
                continue

            sanitized_hint = dict(index_hint)
            sanitized_hint.setdefault("index_type", "btree")
            sanitized_hint.setdefault("is_unique", False)
            sanitized_hint.setdefault(
                "index_name",
                self._build_index_name(scenario_type, table_name, normalized_columns),
            )
            deduped.append(sanitized_hint)
            seen.add(key)

        return deduped

    def _is_redundant_index(self, table: TableInfo, normalized_columns: str) -> bool:
        """Пропустить индексы, которые почти наверняка уже есть из-за PK/UNIQUE."""
        columns = [column.strip() for column in normalized_columns.split(",") if column.strip()]
        if not columns:
            return True
        if columns == [column.lower() for column in table.primary_key]:
            return True
        if len(columns) == 1:
            unique_columns = {column_name.lower() for column_name in table.unique_columns}
            pk_columns = {column_name.lower() for column_name in table.primary_key}
            if columns[0] in pk_columns or columns[0] in unique_columns:
                return True
        return False

    def _build_index_name(self, scenario_type: str, table_name: str, normalized_columns: str) -> str:
        suffix = normalized_columns.replace(",", "_")
        return f"idx_bundle_{scenario_type}_{table_name}_{suffix}"[:255]

    def _build_index_hint(
        self,
        table_name: str,
        column_names: str,
        description: str,
        index_type: str = "btree",
        is_unique: bool = False,
        condition: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "table_name": table_name,
            "column_names": column_names,
            "index_type": index_type,
            "is_unique": is_unique,
            "condition": condition,
            "description": description,
        }

    def _pick_group_column(self, table: TableInfo) -> Optional[ColumnInfo]:
        """Выбрать колонку для GROUP BY."""
        if table.foreign_keys_out:
            column = table.get_column(table.foreign_keys_out[0].from_column)
            if column:
                return column
        string_columns = [column for column in table.columns if column.category == "string" and not column.is_primary_key]
        if string_columns:
            return string_columns[0]
        if table.primary_key:
            return table.get_column(table.primary_key[0])
        return None

    def _pick_metric_column(self, table: TableInfo) -> Optional[ColumnInfo]:
        """Выбрать числовую колонку для агрегирования или range scan."""
        numeric_columns = [
            column for column in table.get_columns_by_category("numeric")
            if not column.is_primary_key
        ]
        if numeric_columns:
            return numeric_columns[0]

        integer_columns = [
            column for column in table.get_columns_by_category("integer")
            if not column.is_primary_key
        ]
        if integer_columns:
            return integer_columns[0]
        return None

    def _pick_mutable_column(self, table: TableInfo, categories: Set[str],
                             metadata: Optional[SchemaMetadata] = None) -> Optional[ColumnInfo]:
        """Выбрать колонку, которую безопасно менять в write-сценариях."""
        foreign_key_columns = {fk.from_column for fk in table.foreign_keys_out}
        heuristic_fk_columns: Set[str] = set()
        if metadata:
            for col in table.columns:
                if col.name in foreign_key_columns:
                    continue
                if col.category in {"integer", "numeric"} and col.name.endswith("_id"):
                    prefix = col.name[:-3]
                    if prefix in metadata.tables:
                        heuristic_fk_columns.add(col.name)

        preferred_name_tokens = (
            "last_update",
            "updated_at",
            "update",
            "modified",
            "status",
            "amount",
            "price",
            "rate",
        )
        candidates = [
            column for column in table.columns
            if column.category in categories
            and not column.is_primary_key
            and not column.is_unique
            and not column.is_partition_key
            and not column.is_auto_generated
            and column.name not in foreign_key_columns
            and column.name not in heuristic_fk_columns
        ]
        for token in preferred_name_tokens:
            for column in candidates:
                if token in column.name.lower():
                    return column
        if categories == {"date"}:
            return None
        return candidates[0] if candidates else None

    def _pick_timestamp_column(self, table: TableInfo) -> Optional[ColumnInfo]:
        """Выбрать наиболее подходящую колонку даты/времени для UPDATE/scan."""
        date_columns = table.get_columns_by_category("date")
        preferred_names = (
            "last_update",
            "updated_at",
            "update",
            "modified",
            "created",
            "timestamp",
            "date",
            "time",
        )
        for column in date_columns:
            lowered_name = column.name.lower()
            if any(token in lowered_name for token in preferred_names):
                return column
        return date_columns[0] if date_columns else None

    def _pick_first_column(self, table: TableInfo, category: str) -> Optional[ColumnInfo]:
        columns = table.get_columns_by_category(category)
        return columns[0] if columns else None

    def _placeholder(self, param_name: str, category: str) -> str:
        """Сформировать placeholder в SQL с учётом quoting для строковых типов."""
        if category in {"string", "date"}:
            return "'{" + param_name + "}'"
        return "{" + param_name + "}"

    def _enrich_fk_mapping_heuristic(
        self,
        metadata: SchemaMetadata,
        table: TableInfo,
        fk_mapping: Dict[str, Any],
    ) -> None:
        """Эвристическое дополнение FK-mapping для колонок *_id без явных FK constraints."""
        from backend.database.schema_analyzer import ForeignKeyInfo

        for column in table.columns:
            if column.name in fk_mapping:
                continue
            if column.category not in {"integer", "numeric"}:
                continue
            if not column.name.endswith("_id"):
                continue
            prefix = column.name[:-3]
            candidate_table = metadata.tables.get(prefix)
            if not candidate_table:
                continue
            pk_col = candidate_table.primary_key_column()
            if pk_col:
                target_column = pk_col.name
            else:
                id_col = next(
                    (c for c in candidate_table.columns if c.name == column.name),
                    None,
                )
                if not id_col:
                    id_col = next(
                        (c for c in candidate_table.columns if c.name.endswith("_id")),
                        None,
                    )
                if not id_col:
                    continue
                target_column = id_col.name

            fk_mapping[column.name] = ForeignKeyInfo(
                constraint_name=f"_heuristic_{table.name}_{column.name}",
                from_table=table.name,
                from_column=column.name,
                to_table=prefix,
                to_column=target_column,
            )

    def _identifier(self, name: str) -> str:
        """Сформировать DBMS-neutral имя таблицы или колонки."""
        return name

    def _random_from_table_param(self, param_name: str, table_name: str, column_name: str) -> Dict[str, Any]:
        return {
            "param_name": param_name,
            "param_type": "random_from_table",
            "table_ref": table_name,
            "column_ref": column_name,
        }

    def _build_query_payload(
        self,
        template: QueryTemplateDefinition,
        sql_template: str,
        description: str,
        params: List[Dict[str, Any]],
        index_hints: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "sql_template": sql_template,
            "query_type": template.query_type,
            "weight": template.default_weight,
            "description": description,
            "params": params,
            "_template_id": template.id,
            "_index_hints": index_hints or [],
        }
