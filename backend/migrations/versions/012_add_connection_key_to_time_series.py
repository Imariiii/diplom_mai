"""Добавление connection_key в time_series

Revision ID: 012
Revises: 011
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("time_series", sa.Column("connection_key", sa.String(length=255), nullable=True))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_time_series_connection_key ON time_series(connection_key)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_time_series_test_conn_ts "
        "ON time_series(test_run_id, connection_key, timestamp)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_time_series_test_conn_ts"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_time_series_connection_key"))
    op.drop_column("time_series", "connection_key")
