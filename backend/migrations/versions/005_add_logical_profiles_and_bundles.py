"""Логические сценарии, профили схем и канонические bundles

Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS schema_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            detection_mode VARCHAR(50) NOT NULL DEFAULT 'hybrid',
            reference_connection_id UUID,
            is_builtin VARCHAR(1) NOT NULL DEFAULT 'f',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_schema_profiles_name ON schema_profiles(name)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_schema_profiles_builtin ON schema_profiles(is_builtin)"))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_schema_profiles_reference_connection_id'
                  AND table_name = 'schema_profiles'
            ) THEN
                ALTER TABLE schema_profiles
                ADD CONSTRAINT fk_schema_profiles_reference_connection_id
                FOREIGN KEY (reference_connection_id)
                REFERENCES db_connection_configs(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
    """))

    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        ADD COLUMN IF NOT EXISTS schema_profile_id UUID
    """))
    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        ADD COLUMN IF NOT EXISTS detected_profile_name VARCHAR(100)
    """))
    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        ADD COLUMN IF NOT EXISTS profile_confidence FLOAT
    """))
    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        ADD COLUMN IF NOT EXISTS profile_source VARCHAR(20) DEFAULT 'auto'
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_db_connection_configs_schema_profile_id'
                  AND table_name = 'db_connection_configs'
            ) THEN
                ALTER TABLE db_connection_configs
                ADD CONSTRAINT fk_db_connection_configs_schema_profile_id
                FOREIGN KEY (schema_profile_id)
                REFERENCES schema_profiles(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_db_conn_configs_schema_profile_id
        ON db_connection_configs(schema_profile_id)
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_templates (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            is_builtin VARCHAR(1) NOT NULL DEFAULT 't',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_templates_builtin ON scenario_templates(is_builtin)"))

    conn.execute(sa.text("""
        INSERT INTO scenario_templates (id, name, description, is_builtin)
        VALUES
            ('read_only', 'Только чтение', 'Преимущественно SELECT, JOIN и range scan без операций записи.', 't'),
            ('write_only', 'Только запись', 'Набор INSERT, UPDATE и DELETE операций без чтения.', 't'),
            ('mixed_light', 'Смешанная лёгкая', 'Смешанная нагрузка с преобладанием чтения и умеренным числом операций записи.', 't'),
            ('mixed_heavy', 'Смешанная тяжёлая', 'Более агрессивная смешанная нагрузка с высокой долей операций записи.', 't'),
            ('oltp', 'OLTP', 'Транзакционная нагрузка короткими операциями с чтением и записью.', 't'),
            ('olap', 'OLAP', 'Аналитическая нагрузка с агрегациями, JOIN и диапазонными чтениями.', 't')
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            is_builtin = EXCLUDED.is_builtin
    """))

    conn.execute(sa.text("""
        INSERT INTO schema_profiles (id, name, description, detection_mode, is_builtin)
        VALUES
            (gen_random_uuid(), 'sakila_like', 'Каталог фильмов и аренды: Sakila, Pagila и совместимые схемы.', 'hybrid', 't'),
            (gen_random_uuid(), 'olist_like', 'E-commerce и заказы маркетплейса: Olist и совместимые схемы.', 'hybrid', 't')
        ON CONFLICT (name) DO UPDATE SET
            description = EXCLUDED.description,
            detection_mode = EXCLUDED.detection_mode,
            is_builtin = EXCLUDED.is_builtin
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_bundles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            schema_profile_id UUID NOT NULL REFERENCES schema_profiles(id) ON DELETE CASCADE,
            scenario_template_id VARCHAR(50) NOT NULL REFERENCES scenario_templates(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            generation_source VARCHAR(50) NOT NULL DEFAULT 'generated_from_reference',
            is_active VARCHAR(1) NOT NULL DEFAULT 't',
            generated_from_connection_id UUID REFERENCES db_connection_configs(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_scenario_bundles_profile_template UNIQUE (schema_profile_id, scenario_template_id)
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundles_profile_id ON scenario_bundles(schema_profile_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundles_template_id ON scenario_bundles(scenario_template_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundles_active ON scenario_bundles(is_active)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_bundle_queries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES scenario_bundles(id) ON DELETE CASCADE,
            sql_template TEXT NOT NULL,
            query_type VARCHAR(20) NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1,
            order_index INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_queries_bundle_id ON scenario_bundle_queries(bundle_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_queries_type ON scenario_bundle_queries(query_type)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_bundle_params (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id UUID NOT NULL REFERENCES scenario_bundle_queries(id) ON DELETE CASCADE,
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
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_params_query_id ON scenario_bundle_params(query_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_params_name ON scenario_bundle_params(param_name)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_bundle_indexes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bundle_id UUID NOT NULL REFERENCES scenario_bundles(id) ON DELETE CASCADE,
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
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_indexes_bundle_id ON scenario_bundle_indexes(bundle_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_bundle_indexes_table_name ON scenario_bundle_indexes(table_name)"))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_bundle_indexes"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_bundle_params"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_bundle_queries"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_bundles"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scenario_templates"))

    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        DROP CONSTRAINT IF EXISTS fk_db_connection_configs_schema_profile_id
    """))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_db_conn_configs_schema_profile_id"))
    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        DROP COLUMN IF EXISTS schema_profile_id,
        DROP COLUMN IF EXISTS detected_profile_name,
        DROP COLUMN IF EXISTS profile_confidence,
        DROP COLUMN IF EXISTS profile_source
    """))

    conn.execute(sa.text("""
        ALTER TABLE schema_profiles
        DROP CONSTRAINT IF EXISTS fk_schema_profiles_reference_connection_id
    """))
    conn.execute(sa.text("DROP TABLE IF EXISTS schema_profiles"))
