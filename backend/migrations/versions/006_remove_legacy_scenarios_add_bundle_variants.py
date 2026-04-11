"""Убрать legacy сценарии и добавить bundle variants

Revision ID: 006
Revises: 005
"""
import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BUILTIN_TEMPLATE_IDS = {
    "read_only",
    "write_only",
    "mixed_light",
    "mixed_heavy",
    "oltp",
    "olap",
}


def _build_custom_template_id(name: str, existing_ids: set[str]) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    base_id = f"custom_{normalized}" if normalized else f"custom_{uuid.uuid4().hex[:8]}"
    candidate = base_id
    suffix = 2
    while candidate in existing_ids or candidate in BUILTIN_TEMPLATE_IDS:
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    existing_ids.add(candidate)
    return candidate


def _migrate_legacy_scenarios(conn) -> None:
    scenarios = conn.execute(sa.text("""
        SELECT
            s.id,
            s.name,
            s.description,
            s.scenario_type,
            s.target_connection_id,
            s.is_builtin,
            dc.schema_profile_id
        FROM test_scenarios s
        LEFT JOIN db_connection_configs dc ON dc.id = s.target_connection_id
        WHERE s.is_builtin = 'f'
        ORDER BY s.created_at
    """)).mappings().all()
    if not scenarios:
        return

    existing_template_ids = {
        row["id"]
        for row in conn.execute(sa.text("SELECT id FROM scenario_templates")).mappings().all()
    }

    for scenario in scenarios:
        schema_profile_id = scenario["schema_profile_id"]
        if not schema_profile_id:
            print(
                f"[MIGRATION 006] Пропуск legacy сценария '{scenario['name']}': "
                "не удалось определить schema_profile_id"
            )
            continue

        if scenario["scenario_type"] in BUILTIN_TEMPLATE_IDS:
            template_id = scenario["scenario_type"]
        else:
            template_id = _build_custom_template_id(scenario["name"], existing_template_ids)
            conn.execute(
                sa.text("""
                    INSERT INTO scenario_templates (id, name, description, is_builtin, created_at, updated_at)
                    VALUES (:id, :name, :description, 'f', now(), now())
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": template_id,
                    "name": scenario["name"],
                    "description": scenario["description"],
                },
            )

        has_active_bundle = conn.execute(
            sa.text("""
                SELECT 1
                FROM scenario_bundles
                WHERE schema_profile_id = :schema_profile_id
                  AND scenario_template_id = :scenario_template_id
                  AND is_active = 't'
                LIMIT 1
            """),
            {
                "schema_profile_id": schema_profile_id,
                "scenario_template_id": template_id,
            },
        ).scalar()

        bundle_id = str(uuid.uuid4())
        conn.execute(
            sa.text("""
                INSERT INTO scenario_bundles (
                    id,
                    schema_profile_id,
                    scenario_template_id,
                    name,
                    description,
                    generation_source,
                    is_builtin,
                    is_active,
                    generated_from_connection_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id,
                    :schema_profile_id,
                    :scenario_template_id,
                    :name,
                    :description,
                    'migrated_from_legacy',
                    'f',
                    :is_active,
                    :generated_from_connection_id,
                    now(),
                    now()
                )
            """),
            {
                "id": bundle_id,
                "schema_profile_id": schema_profile_id,
                "scenario_template_id": template_id,
                "name": scenario["name"],
                "description": scenario["description"],
                "is_active": 'f' if has_active_bundle else 't',
                "generated_from_connection_id": scenario["target_connection_id"],
            },
        )

        queries = conn.execute(
            sa.text("""
                SELECT id, sql_template, query_type, weight, order_index, description
                FROM scenario_queries
                WHERE scenario_id = :scenario_id
                ORDER BY order_index, created_at
            """),
            {"scenario_id": scenario["id"]},
        ).mappings().all()

        for query in queries:
            bundle_query_id = str(uuid.uuid4())
            conn.execute(
                sa.text("""
                    INSERT INTO scenario_bundle_queries (
                        id,
                        bundle_id,
                        sql_template,
                        query_type,
                        weight,
                        order_index,
                        description,
                        created_at
                    )
                    VALUES (
                        :id,
                        :bundle_id,
                        :sql_template,
                        :query_type,
                        :weight,
                        :order_index,
                        :description,
                        now()
                    )
                """),
                {
                    "id": bundle_query_id,
                    "bundle_id": bundle_id,
                    "sql_template": query["sql_template"],
                    "query_type": query["query_type"],
                    "weight": query["weight"],
                    "order_index": query["order_index"],
                    "description": query["description"],
                },
            )

            params = conn.execute(
                sa.text("""
                    SELECT
                        param_name,
                        param_type,
                        min_value,
                        max_value,
                        string_pattern,
                        string_length,
                        table_ref,
                        column_ref,
                        current_value,
                        step
                    FROM scenario_params
                    WHERE query_id = :query_id
                    ORDER BY created_at
                """),
                {"query_id": query["id"]},
            ).mappings().all()
            for param in params:
                conn.execute(
                    sa.text("""
                        INSERT INTO scenario_bundle_params (
                            id,
                            query_id,
                            param_name,
                            param_type,
                            min_value,
                            max_value,
                            string_pattern,
                            string_length,
                            table_ref,
                            column_ref,
                            current_value,
                            step,
                            created_at
                        )
                        VALUES (
                            :id,
                            :query_id,
                            :param_name,
                            :param_type,
                            :min_value,
                            :max_value,
                            :string_pattern,
                            :string_length,
                            :table_ref,
                            :column_ref,
                            :current_value,
                            :step,
                            now()
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "query_id": bundle_query_id,
                        "param_name": param["param_name"],
                        "param_type": param["param_type"],
                        "min_value": param["min_value"],
                        "max_value": param["max_value"],
                        "string_pattern": param["string_pattern"],
                        "string_length": param["string_length"],
                        "table_ref": param["table_ref"],
                        "column_ref": param["column_ref"],
                        "current_value": param["current_value"],
                        "step": param["step"],
                    },
                )

        indexes = conn.execute(
            sa.text("""
                SELECT
                    table_name,
                    column_names,
                    index_type,
                    index_name,
                    is_unique,
                    condition,
                    description
                FROM scenario_indexes
                WHERE scenario_id = :scenario_id
                ORDER BY created_at
            """),
            {"scenario_id": scenario["id"]},
        ).mappings().all()
        for index in indexes:
            conn.execute(
                sa.text("""
                    INSERT INTO scenario_bundle_indexes (
                        id,
                        bundle_id,
                        table_name,
                        column_names,
                        index_type,
                        index_name,
                        is_unique,
                        condition,
                        description,
                        created_at
                    )
                    VALUES (
                        :id,
                        :bundle_id,
                        :table_name,
                        :column_names,
                        :index_type,
                        :index_name,
                        :is_unique,
                        :condition,
                        :description,
                        now()
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "bundle_id": bundle_id,
                    "table_name": index["table_name"],
                    "column_names": index["column_names"],
                    "index_type": index["index_type"],
                    "index_name": index["index_name"],
                    "is_unique": index["is_unique"],
                    "condition": index["condition"],
                    "description": index["description"],
                },
            )


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE scenario_templates
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()
    """))
    conn.execute(sa.text("""
        UPDATE scenario_templates
        SET updated_at = COALESCE(updated_at, created_at, now())
    """))

    conn.execute(sa.text("""
        ALTER TABLE scenario_bundles
        ADD COLUMN IF NOT EXISTS description TEXT
    """))
    conn.execute(sa.text("""
        ALTER TABLE scenario_bundles
        ADD COLUMN IF NOT EXISTS is_builtin VARCHAR(1) NOT NULL DEFAULT 'f'
    """))
    conn.execute(sa.text("""
        UPDATE scenario_bundles
        SET is_builtin = 't'
        WHERE is_builtin IS DISTINCT FROM 't'
    """))
    conn.execute(sa.text("""
        ALTER TABLE scenario_bundles
        DROP CONSTRAINT IF EXISTS uq_scenario_bundles_profile_template
    """))
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_scenario_bundles_profile_template_active"))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_scenario_bundles_builtin
        ON scenario_bundles(is_builtin)
    """))

    _migrate_legacy_scenarios(conn)

    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_bundles_profile_template_active
        ON scenario_bundles(schema_profile_id, scenario_template_id)
        WHERE is_active = 't'
    """))

    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_params"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_queries"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_indexes"))
    conn.execute(sa.text("DROP TABLE IF EXISTS test_scenarios"))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DROP INDEX IF EXISTS uq_scenario_bundles_profile_template_active"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_scenario_bundles_builtin"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS test_scenarios (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            scenario_type VARCHAR(50) NOT NULL,
            target_connection_id UUID REFERENCES db_connection_configs(id) ON DELETE CASCADE,
            is_builtin VARCHAR(1) NOT NULL DEFAULT 'f',
            is_active VARCHAR(1) NOT NULL DEFAULT 't',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_queries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scenario_id UUID NOT NULL REFERENCES test_scenarios(id) ON DELETE CASCADE,
            sql_template TEXT NOT NULL,
            query_type VARCHAR(20) NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1,
            order_index INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_params (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id UUID NOT NULL REFERENCES scenario_queries(id) ON DELETE CASCADE,
            param_name VARCHAR(100) NOT NULL,
            param_type VARCHAR(50) NOT NULL,
            min_value INTEGER,
            max_value INTEGER,
            string_pattern VARCHAR(255),
            string_length INTEGER,
            table_ref VARCHAR(100),
            column_ref VARCHAR(100),
            current_value INTEGER DEFAULT 0,
            step INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_indexes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scenario_id UUID NOT NULL REFERENCES test_scenarios(id) ON DELETE CASCADE,
            table_name VARCHAR(100) NOT NULL,
            column_names VARCHAR(500) NOT NULL,
            index_type VARCHAR(50) NOT NULL DEFAULT 'btree',
            index_name VARCHAR(255),
            is_unique VARCHAR(1) NOT NULL DEFAULT 'f',
            condition TEXT,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(sa.text("""
        ALTER TABLE scenario_bundles
        DROP COLUMN IF EXISTS description
    """))
    conn.execute(sa.text("""
        ALTER TABLE scenario_bundles
        DROP COLUMN IF EXISTS is_builtin
    """))
    conn.execute(sa.text("""
        ALTER TABLE scenario_templates
        DROP COLUMN IF EXISTS updated_at
    """))
