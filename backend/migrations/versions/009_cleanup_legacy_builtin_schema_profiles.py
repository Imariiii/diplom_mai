"""Убрать legacy builtin schema_profiles

Revision ID: 009
Revises: 008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        UPDATE schema_profiles AS sp
        SET is_builtin = 'f',
            updated_at = now()
        WHERE sp.name IN ('sakila_like', 'olist_like')
          AND sp.is_builtin = 't'
          AND (
              sp.reference_connection_id IS NOT NULL
              OR EXISTS (
                  SELECT 1
                  FROM db_connection_configs AS dc
                  WHERE dc.schema_profile_id = sp.id
              )
              OR EXISTS (
                  SELECT 1
                  FROM logical_databases AS ld
                  WHERE ld.schema_profile_id = sp.id
              )
              OR EXISTS (
                  SELECT 1
                  FROM scenario_bundles AS sb
                  WHERE sb.schema_profile_id = sp.id
              )
          )
    """))

    conn.execute(sa.text("""
        DELETE FROM schema_profiles AS sp
        WHERE sp.name IN ('sakila_like', 'olist_like')
          AND sp.is_builtin = 't'
          AND sp.reference_connection_id IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM db_connection_configs AS dc
              WHERE dc.schema_profile_id = sp.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM logical_databases AS ld
              WHERE ld.schema_profile_id = sp.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM scenario_bundles AS sb
              WHERE sb.schema_profile_id = sp.id
          )
    """))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        UPDATE schema_profiles
        SET is_builtin = 't',
            updated_at = now()
        WHERE name IN ('sakila_like', 'olist_like')
    """))
