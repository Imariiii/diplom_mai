"""Привязка сценариев к конкретному подключению

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE test_scenarios
        ADD COLUMN IF NOT EXISTS target_connection_id UUID
    """))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_test_scenarios_target_connection_id'
                  AND table_name = 'test_scenarios'
            ) THEN
                ALTER TABLE test_scenarios
                ADD CONSTRAINT fk_test_scenarios_target_connection_id
                FOREIGN KEY (target_connection_id)
                REFERENCES db_connection_configs(id)
                ON DELETE CASCADE;
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_test_scenarios_target_connection_id
        ON test_scenarios(target_connection_id)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE test_scenarios
        DROP CONSTRAINT IF EXISTS fk_test_scenarios_target_connection_id
    """))
    conn.execute(sa.text("""
        DROP INDEX IF EXISTS idx_test_scenarios_target_connection_id
    """))
    conn.execute(sa.text("""
        ALTER TABLE test_scenarios
        DROP COLUMN IF EXISTS target_connection_id
    """))
