"""Добавление transaction bundle: workload_mode и таблицы транзакций

Revision ID: 013
Revises: 012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
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


def _has_index(table_name: str, index_name: str) -> bool:
    """Проверить наличие индекса для повторного запуска миграции."""
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_column("scenario_bundles", "workload_mode"):
        op.add_column(
            "scenario_bundles",
            sa.Column("workload_mode", sa.String(length=20), nullable=False, server_default="query"),
        )
    op.execute(sa.text("UPDATE scenario_bundles SET workload_mode = 'query' WHERE workload_mode IS NULL"))

    if not _has_table("scenario_bundle_transactions"):
        op.create_table(
            "scenario_bundle_transactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "bundle_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("scenario_bundles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_index("scenario_bundle_transactions", "idx_scenario_bundle_transactions_bundle_id"):
        op.create_index(
            "idx_scenario_bundle_transactions_bundle_id",
            "scenario_bundle_transactions",
            ["bundle_id"],
        )

    if not _has_table("scenario_bundle_transaction_steps"):
        op.create_table(
            "scenario_bundle_transaction_steps",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "transaction_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("scenario_bundle_transactions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sql_template", sa.Text(), nullable=False),
            sa.Column("query_type", sa.String(length=20), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_index("scenario_bundle_transaction_steps", "idx_scenario_bundle_transaction_steps_tx_id"):
        op.create_index(
            "idx_scenario_bundle_transaction_steps_tx_id",
            "scenario_bundle_transaction_steps",
            ["transaction_id"],
        )

    if not _has_table("scenario_bundle_transaction_params"):
        op.create_table(
            "scenario_bundle_transaction_params",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "transaction_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("scenario_bundle_transactions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("param_name", sa.String(length=100), nullable=False),
            sa.Column("param_type", sa.String(length=50), nullable=False),
            sa.Column("min_value", sa.Integer(), nullable=True),
            sa.Column("max_value", sa.Integer(), nullable=True),
            sa.Column("string_pattern", sa.String(length=255), nullable=True),
            sa.Column("string_length", sa.Integer(), nullable=True),
            sa.Column("table_ref", sa.String(length=100), nullable=True),
            sa.Column("column_ref", sa.String(length=100), nullable=True),
            sa.Column("current_value", sa.Integer(), nullable=True),
            sa.Column("step", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_index("scenario_bundle_transaction_params", "idx_scenario_bundle_transaction_params_tx_id"):
        op.create_index(
            "idx_scenario_bundle_transaction_params_tx_id",
            "scenario_bundle_transaction_params",
            ["transaction_id"],
        )
    if not _has_index("scenario_bundle_transaction_params", "idx_scenario_bundle_transaction_params_name"):
        op.create_index(
            "idx_scenario_bundle_transaction_params_name",
            "scenario_bundle_transaction_params",
            ["param_name"],
        )


def downgrade() -> None:
    op.drop_index("idx_scenario_bundle_transaction_params_name", table_name="scenario_bundle_transaction_params")
    op.drop_index("idx_scenario_bundle_transaction_params_tx_id", table_name="scenario_bundle_transaction_params")
    op.drop_table("scenario_bundle_transaction_params")
    op.drop_index("idx_scenario_bundle_transaction_steps_tx_id", table_name="scenario_bundle_transaction_steps")
    op.drop_table("scenario_bundle_transaction_steps")
    op.drop_index("idx_scenario_bundle_transactions_bundle_id", table_name="scenario_bundle_transactions")
    op.drop_table("scenario_bundle_transactions")
    op.drop_column("scenario_bundles", "workload_mode")
