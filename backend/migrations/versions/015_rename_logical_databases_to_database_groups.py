"""Переименование logical_databases → database_groups

Revision ID: 015
Revises: 014
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_constraint_if_exists(table: str, old_name: str, new_name: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = '{old_name}' AND table_name = '{table}'
            ) THEN
                ALTER TABLE {table} RENAME CONSTRAINT {old_name} TO {new_name};
            END IF;
        END $$;
    """))


def _rename_index_if_exists(old_name: str, new_name: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'i' AND c.relname = '{old_name}'
            ) THEN
                ALTER INDEX {old_name} RENAME TO {new_name};
            END IF;
        END $$;
    """))


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("ALTER TABLE logical_databases RENAME TO database_groups"))

    conn.execute(sa.text(
        "ALTER TABLE db_connection_configs "
        "RENAME COLUMN logical_database_id TO database_group_id"
    ))
    conn.execute(sa.text(
        "ALTER TABLE test_runs RENAME COLUMN logical_database_id TO database_group_id"
    ))

    _rename_constraint_if_exists(
        "db_connection_configs",
        "fk_db_conn_configs_logical_database_id",
        "fk_db_conn_configs_database_group_id",
    )
    _rename_constraint_if_exists(
        "database_groups",
        "fk_logical_databases_schema_profile_id",
        "fk_database_groups_schema_profile_id",
    )
    _rename_constraint_if_exists(
        "database_groups",
        "fk_logical_databases_reference_connection_id",
        "fk_database_groups_reference_connection_id",
    )

    _rename_index_if_exists("idx_logical_databases_name", "idx_database_groups_name")
    _rename_index_if_exists(
        "idx_logical_databases_schema_profile_id",
        "idx_database_groups_schema_profile_id",
    )
    _rename_index_if_exists(
        "idx_logical_databases_reference_connection_id",
        "idx_database_groups_reference_connection_id",
    )
    _rename_index_if_exists(
        "idx_logical_databases_profile_status",
        "idx_database_groups_profile_status",
    )
    _rename_index_if_exists(
        "idx_logical_databases_compatibility_status",
        "idx_database_groups_compatibility_status",
    )
    _rename_index_if_exists(
        "idx_db_conn_configs_logical_db_id",
        "idx_db_conn_configs_database_group_id",
    )
    _rename_index_if_exists(
        "idx_test_runs_logical_db_id",
        "idx_test_runs_database_group_id",
    )


def downgrade() -> None:
    _rename_index_if_exists("idx_test_runs_database_group_id", "idx_test_runs_logical_db_id")
    _rename_index_if_exists(
        "idx_db_conn_configs_database_group_id",
        "idx_db_conn_configs_logical_db_id",
    )
    _rename_index_if_exists(
        "idx_database_groups_compatibility_status",
        "idx_logical_databases_compatibility_status",
    )
    _rename_index_if_exists(
        "idx_database_groups_profile_status",
        "idx_logical_databases_profile_status",
    )
    _rename_index_if_exists(
        "idx_database_groups_reference_connection_id",
        "idx_logical_databases_reference_connection_id",
    )
    _rename_index_if_exists(
        "idx_database_groups_schema_profile_id",
        "idx_logical_databases_schema_profile_id",
    )
    _rename_index_if_exists("idx_database_groups_name", "idx_logical_databases_name")

    _rename_constraint_if_exists(
        "database_groups",
        "fk_database_groups_reference_connection_id",
        "fk_logical_databases_reference_connection_id",
    )
    _rename_constraint_if_exists(
        "database_groups",
        "fk_database_groups_schema_profile_id",
        "fk_logical_databases_schema_profile_id",
    )
    _rename_constraint_if_exists(
        "db_connection_configs",
        "fk_db_conn_configs_database_group_id",
        "fk_db_conn_configs_logical_database_id",
    )

    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE test_runs RENAME COLUMN database_group_id TO logical_database_id"
    ))
    conn.execute(sa.text(
        "ALTER TABLE db_connection_configs "
        "RENAME COLUMN database_group_id TO logical_database_id"
    ))
    conn.execute(sa.text("ALTER TABLE database_groups RENAME TO logical_databases"))
