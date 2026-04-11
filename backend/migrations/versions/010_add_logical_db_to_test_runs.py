"""Добавление привязки тестов к логической базе данных

Revision ID: 010
Revises: 009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        ALTER TABLE test_runs
        ADD COLUMN IF NOT EXISTS logical_database_id UUID
            REFERENCES logical_databases(id) ON DELETE SET NULL
    """))

    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_test_runs_logical_db_id
        ON test_runs (logical_database_id)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS idx_test_runs_logical_db_id"))
    conn.execute(sa.text("ALTER TABLE test_runs DROP COLUMN IF EXISTS logical_database_id"))
