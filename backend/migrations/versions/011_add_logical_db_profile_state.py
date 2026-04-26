"""Добавить состояние профиля и совместимости logical database

Revision ID: 011
Revises: 010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS reference_connection_id UUID
    """))
    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS profile_status VARCHAR(30) NOT NULL DEFAULT 'draft'
    """))
    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS compatibility_status VARCHAR(30) NOT NULL DEFAULT 'unknown'
    """))
    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS compatibility_report JSON
    """))
    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ
    """))

    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_logical_databases_reference_connection_id'
                  AND table_name = 'logical_databases'
            ) THEN
                ALTER TABLE logical_databases
                ADD CONSTRAINT fk_logical_databases_reference_connection_id
                FOREIGN KEY (reference_connection_id)
                REFERENCES db_connection_configs(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_logical_databases_reference_connection_id "
        "ON logical_databases(reference_connection_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_logical_databases_profile_status "
        "ON logical_databases(profile_status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_logical_databases_compatibility_status "
        "ON logical_databases(compatibility_status)"
    ))

    conn.execute(sa.text("""
        UPDATE logical_databases AS ld
        SET reference_connection_id = sp.reference_connection_id
        FROM schema_profiles AS sp
        WHERE ld.schema_profile_id = sp.id
          AND ld.reference_connection_id IS NULL
          AND sp.reference_connection_id IS NOT NULL
    """))

    conn.execute(sa.text("""
        UPDATE logical_databases AS ld
        SET reference_connection_id = picked.connection_id
        FROM (
            SELECT DISTINCT ON (logical_database_id)
                logical_database_id,
                id AS connection_id
            FROM db_connection_configs
            WHERE logical_database_id IS NOT NULL
              AND is_active = 't'
            ORDER BY logical_database_id, name
        ) AS picked
        WHERE ld.id = picked.logical_database_id
          AND ld.reference_connection_id IS NULL
    """))

    conn.execute(sa.text("""
        UPDATE logical_databases
        SET profile_status = CASE
                WHEN schema_profile_id IS NOT NULL THEN 'needs_review'
                ELSE 'draft'
            END,
            compatibility_status = CASE
                WHEN schema_profile_id IS NOT NULL THEN 'unknown'
                ELSE 'unknown'
            END
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_logical_databases_compatibility_status"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_logical_databases_profile_status"))
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_logical_databases_reference_connection_id"))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_logical_databases_reference_connection_id'
                  AND table_name = 'logical_databases'
            ) THEN
                ALTER TABLE logical_databases
                DROP CONSTRAINT fk_logical_databases_reference_connection_id;
            END IF;
        END $$;
    """))
    conn.execute(sa.text("ALTER TABLE logical_databases DROP COLUMN IF EXISTS validated_at"))
    conn.execute(sa.text("ALTER TABLE logical_databases DROP COLUMN IF EXISTS compatibility_report"))
    conn.execute(sa.text("ALTER TABLE logical_databases DROP COLUMN IF EXISTS compatibility_status"))
    conn.execute(sa.text("ALTER TABLE logical_databases DROP COLUMN IF EXISTS profile_status"))
    conn.execute(sa.text("ALTER TABLE logical_databases DROP COLUMN IF EXISTS reference_connection_id"))
