"""Перевод OLTP bundle в ручной transaction mode

Revision ID: 017
Revises: 016
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from backend.database.oltp_transaction_seeds import apply_oltp_transaction_migration

    conn = op.get_bind()
    apply_oltp_transaction_migration(conn)


def downgrade() -> None:
    import sqlalchemy as sa

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE scenario_templates SET is_builtin = 't', updated_at = now() "
            "WHERE id = 'oltp'"
        )
    )
