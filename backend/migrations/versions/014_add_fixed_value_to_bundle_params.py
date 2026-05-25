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


def _has_table(table_name: str) -> bool:
    """Проверить наличие таблицы для повторного запуска миграции."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    """Проверить наличие колонки для повторного запуска миграции."""
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("scenario_bundle_params", "fixed_value"):
        op.add_column(
            "scenario_bundle_params",
            sa.Column("fixed_value", sa.String(length=255), nullable=True),
        )
    if not _has_column("scenario_bundle_transaction_params", "fixed_value"):
        op.add_column(
            "scenario_bundle_transaction_params",
            sa.Column("fixed_value", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("scenario_bundle_transaction_params", "fixed_value")
    op.drop_column("scenario_bundle_params", "fixed_value")
