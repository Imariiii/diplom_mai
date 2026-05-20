"""Добавление measurement_phase в metric_samples

Revision ID: 016
Revises: 015
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "metric_samples",
        sa.Column("measurement_phase", sa.String(length=32), nullable=True),
    )
    op.execute(sa.text(
        "UPDATE metric_samples SET measurement_phase = 'measurement' "
        "WHERE measurement_phase IS NULL"
    ))


def downgrade() -> None:
    op.drop_column("metric_samples", "measurement_phase")
