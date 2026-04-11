"""Логические базы данных — датасет без привязки к СУБД

Revision ID: 007
Revises: 006
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS logical_databases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_logical_databases_name ON logical_databases(name)"
    ))

    conn.execute(sa.text("""
        ALTER TABLE db_connection_configs
        ADD COLUMN IF NOT EXISTS logical_database_id UUID
    """))

    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_db_conn_configs_logical_database_id'
                  AND table_name = 'db_connection_configs'
            ) THEN
                ALTER TABLE db_connection_configs
                ADD CONSTRAINT fk_db_conn_configs_logical_database_id
                FOREIGN KEY (logical_database_id)
                REFERENCES logical_databases(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_db_conn_configs_logical_db_id ON db_connection_configs(logical_database_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "DROP INDEX IF EXISTS idx_db_conn_configs_logical_db_id"
    ))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_db_conn_configs_logical_database_id'
                  AND table_name = 'db_connection_configs'
            ) THEN
                ALTER TABLE db_connection_configs
                DROP CONSTRAINT fk_db_conn_configs_logical_database_id;
            END IF;
        END $$;
    """))
    conn.execute(sa.text(
        "ALTER TABLE db_connection_configs DROP COLUMN IF EXISTS logical_database_id"
    ))
    conn.execute(sa.text("DROP TABLE IF EXISTS logical_databases"))
