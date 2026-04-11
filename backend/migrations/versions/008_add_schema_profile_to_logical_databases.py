"""Привязать logical_databases к schema_profiles

Revision ID: 008
Revises: 007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE logical_databases
        ADD COLUMN IF NOT EXISTS schema_profile_id UUID
    """))

    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_logical_databases_schema_profile_id'
                  AND table_name = 'logical_databases'
            ) THEN
                ALTER TABLE logical_databases
                ADD CONSTRAINT fk_logical_databases_schema_profile_id
                FOREIGN KEY (schema_profile_id)
                REFERENCES schema_profiles(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_logical_databases_schema_profile_id ON logical_databases(schema_profile_id)"
    ))

    conn.execute(sa.text("""
        UPDATE logical_databases AS ld
        SET schema_profile_id = profiles.schema_profile_id
        FROM (
            SELECT
                logical_database_id,
                MIN(schema_profile_id::text)::uuid AS schema_profile_id
            FROM db_connection_configs
            WHERE logical_database_id IS NOT NULL
              AND schema_profile_id IS NOT NULL
            GROUP BY logical_database_id
            HAVING COUNT(DISTINCT schema_profile_id) = 1
        ) AS profiles
        WHERE ld.id = profiles.logical_database_id
          AND ld.schema_profile_id IS NULL
    """))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "DROP INDEX IF EXISTS idx_logical_databases_schema_profile_id"
    ))

    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_logical_databases_schema_profile_id'
                  AND table_name = 'logical_databases'
            ) THEN
                ALTER TABLE logical_databases
                DROP CONSTRAINT fk_logical_databases_schema_profile_id;
            END IF;
        END $$;
    """))

    conn.execute(sa.text(
        "ALTER TABLE logical_databases DROP COLUMN IF EXISTS schema_profile_id"
    ))
