"""
Библиотека шаблонов SQL-запросов для автогенерации сценариев.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class TemplateRequirements:
    """Ограничения применимости шаблона к таблице."""

    has_single_pk: bool = False
    has_fk_out: bool = False
    has_fk_in_or_out: bool = False
    has_numeric_column: bool = False
    has_date_column: bool = False
    has_timestamp_column: bool = False
    insert_safe: bool = False
    delete_safe: bool = False
    min_rows: int = 0


@dataclass(frozen=True)
class QueryTemplateDefinition:
    """Описание абстрактного шаблона запроса."""

    id: str
    name: str
    description: str
    pattern: str
    query_type: str
    scenario_types: List[str]
    complexity: str
    default_weight: int
    requirements: TemplateRequirements = field(default_factory=TemplateRequirements)


QUERY_TEMPLATES: List[QueryTemplateDefinition] = [
    QueryTemplateDefinition(
        id="select_by_pk",
        name="SELECT по primary key",
        description="Быстрое чтение одной строки по первичному ключу.",
        pattern="SELECT * FROM {table} WHERE {pk_column} = {pk_value}",
        query_type="select",
        scenario_types=["read_only", "mixed_light", "mixed_heavy", "oltp"],
        complexity="simple",
        default_weight=30,
        requirements=TemplateRequirements(has_single_pk=True, min_rows=10),
    ),
    QueryTemplateDefinition(
        id="select_projection_by_pk",
        name="SELECT подмножества колонок",
        description="Чтение нескольких прикладных колонок по первичному ключу.",
        pattern="SELECT {projection_columns} FROM {table} WHERE {pk_column} = {pk_value}",
        query_type="select",
        scenario_types=["read_only", "oltp"],
        complexity="simple",
        default_weight=20,
        requirements=TemplateRequirements(has_single_pk=True, min_rows=10),
    ),
    QueryTemplateDefinition(
        id="select_by_fk",
        name="SELECT по foreign key",
        description="Чтение строк по значению внешнего ключа.",
        pattern="SELECT * FROM {table} WHERE {fk_column} = {fk_value} LIMIT 100",
        query_type="select",
        scenario_types=["read_only", "mixed_light", "mixed_heavy", "oltp"],
        complexity="simple",
        default_weight=15,
        requirements=TemplateRequirements(has_fk_out=True, min_rows=10),
    ),
    QueryTemplateDefinition(
        id="select_join_fk",
        name="JOIN по foreign key",
        description="Чтение с одним JOIN через существующую FK-связь.",
        pattern=(
            "SELECT a.*, b.* FROM {table_a} a "
            "JOIN {table_b} b ON a.{fk_column} = b.{ref_column} "
            "WHERE a.{pk_column} = {pk_value}"
        ),
        query_type="select",
        scenario_types=["read_only", "mixed_light", "mixed_heavy", "oltp", "olap"],
        complexity="medium",
        default_weight=20,
        requirements=TemplateRequirements(has_single_pk=True, has_fk_out=True, min_rows=10),
    ),
    QueryTemplateDefinition(
        id="select_join_chain",
        name="Цепочка JOIN",
        description="Чтение с двумя JOIN по цепочке FK.",
        pattern=(
            "SELECT a.*, b.*, c.* FROM {table_a} a "
            "JOIN {table_b} b ON a.{fk_ab} = b.{ref_ab} "
            "JOIN {table_c} c ON b.{fk_bc} = c.{ref_bc} "
            "WHERE a.{pk_column} = {pk_value}"
        ),
        query_type="select",
        scenario_types=["olap", "read_only"],
        complexity="complex",
        default_weight=15,
        requirements=TemplateRequirements(has_single_pk=True, has_fk_out=True, min_rows=10),
    ),
    QueryTemplateDefinition(
        id="aggregation_count_group",
        name="COUNT и GROUP BY",
        description="Агрегация количества строк по связующей колонке.",
        pattern="SELECT {group_column}, COUNT(*) AS item_count FROM {table} GROUP BY {group_column} ORDER BY item_count DESC",
        query_type="select",
        scenario_types=["read_only", "olap"],
        complexity="medium",
        default_weight=20,
        requirements=TemplateRequirements(has_fk_in_or_out=True, min_rows=100),
    ),
    QueryTemplateDefinition(
        id="aggregation_sum_numeric",
        name="SUM/AVG по числовой колонке",
        description="Агрегация числовых значений с группировкой.",
        pattern=(
            "SELECT {group_column}, COUNT(*) AS row_count, "
            "SUM({metric_column}) AS total_value, AVG({metric_column}) AS avg_value "
            "FROM {table} GROUP BY {group_column} ORDER BY total_value DESC"
        ),
        query_type="select",
        scenario_types=["olap", "read_only"],
        complexity="medium",
        default_weight=20,
        requirements=TemplateRequirements(has_numeric_column=True, has_fk_in_or_out=True, min_rows=100),
    ),
    QueryTemplateDefinition(
        id="range_scan_date",
        name="Range scan по дате",
        description="Диапазонное чтение по колонке даты или времени.",
        pattern="SELECT * FROM {table} WHERE {date_column} >= {threshold_value} ORDER BY {date_column} LIMIT 100",
        query_type="select",
        scenario_types=["read_only", "olap"],
        complexity="medium",
        default_weight=15,
        requirements=TemplateRequirements(has_date_column=True, min_rows=100),
    ),
    QueryTemplateDefinition(
        id="range_scan_numeric",
        name="Range scan по числовой колонке",
        description="Диапазонное чтение по числовому столбцу.",
        pattern="SELECT * FROM {table} WHERE {numeric_column} >= {threshold_value} ORDER BY {numeric_column} LIMIT 100",
        query_type="select",
        scenario_types=["read_only", "olap"],
        complexity="medium",
        default_weight=15,
        requirements=TemplateRequirements(has_numeric_column=True, min_rows=100),
    ),
    QueryTemplateDefinition(
        id="update_timestamp_by_pk",
        name="UPDATE timestamp-поля",
        description="Обновление временной метки записи по primary key.",
        pattern="UPDATE {table} SET {target_column} = {current_timestamp} WHERE {pk_column} = {pk_value}",
        query_type="update",
        scenario_types=["write_only", "mixed_light", "mixed_heavy", "oltp"],
        complexity="simple",
        default_weight=20,
        requirements=TemplateRequirements(has_single_pk=True, has_timestamp_column=True),
    ),
    QueryTemplateDefinition(
        id="update_numeric_by_pk",
        name="UPDATE числового поля",
        description="Инкремент числового поля по primary key.",
        pattern="UPDATE {table} SET {target_column} = {target_column} + 1 WHERE {pk_column} = {pk_value}",
        query_type="update",
        scenario_types=["write_only", "mixed_light", "mixed_heavy"],
        complexity="simple",
        default_weight=20,
        requirements=TemplateRequirements(has_single_pk=True, has_numeric_column=True),
    ),
    QueryTemplateDefinition(
        id="insert_basic",
        name="INSERT строки",
        description="Вставка новой строки в таблицу с безопасно подобранными колонками.",
        pattern="INSERT INTO {table} ({columns}) VALUES ({values})",
        query_type="insert",
        scenario_types=["write_only", "mixed_light", "mixed_heavy", "oltp"],
        complexity="medium",
        default_weight=15,
        requirements=TemplateRequirements(insert_safe=True),
    ),
    QueryTemplateDefinition(
        id="delete_by_pk",
        name="DELETE по primary key",
        description="Удаление строки из листовой таблицы по primary key.",
        pattern="DELETE FROM {table} WHERE {pk_column} = {pk_value}",
        query_type="delete",
        scenario_types=["write_only", "mixed_heavy"],
        complexity="simple",
        default_weight=10,
        requirements=TemplateRequirements(has_single_pk=True, delete_safe=True),
    ),
]


QUERY_TEMPLATES_BY_ID: Dict[str, QueryTemplateDefinition] = {
    template.id: template
    for template in QUERY_TEMPLATES
}
