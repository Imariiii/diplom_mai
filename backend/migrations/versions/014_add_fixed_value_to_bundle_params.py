"""Добавление fixed_value для параметров bundle (query и transaction)

Revision ID: 014
Revises: 013
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scenario_bundle_params",
        sa.Column("fixed_value", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "scenario_bundle_transaction_params",
        sa.Column("fixed_value", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scenario_bundle_transaction_params", "fixed_value")
    op.drop_column("scenario_bundle_params", "fixed_value")
