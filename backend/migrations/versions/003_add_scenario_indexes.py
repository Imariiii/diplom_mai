"""Добавление индексов сценариев тестирования

Revision ID: 003
Revises: 002
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUILTIN_SCENARIO_INDEXES = {
    "read_only": [
        {
            "table_name": "film_category",
            "column_names": "film_id",
            "index_type": "btree",
            "description": "Ускоряет JOIN между film и film_category",
        },
        {
            "table_name": "payment",
            "column_names": "rental_id",
            "index_type": "btree",
            "description": "Ускоряет JOIN между rental и payment",
        },
        {
            "table_name": "rental",
            "column_names": "customer_id",
            "index_type": "btree",
            "description": "Ускоряет фильтрацию rental по customer_id",
        },
    ],
    "write_only": [
        {
            "table_name": "actor",
            "column_names": "last_update",
            "index_type": "btree",
            "description": "Дополнительный индекс для сценария write_only",
        },
        {
            "table_name": "film",
            "column_names": "rental_rate",
            "index_type": "btree",
            "description": "Дополнительный индекс для сценария write_only",
        },
        {
            "table_name": "customer",
            "column_names": "last_update",
            "index_type": "btree",
            "description": "Дополнительный индекс для сценария write_only",
        },
    ],
    "mixed_light": [
        {
            "table_name": "film_category",
            "column_names": "film_id",
            "index_type": "btree",
            "description": "Ускоряет JOIN между film и film_category",
        },
        {
            "table_name": "rental",
            "column_names": "customer_id",
            "index_type": "btree",
            "description": "Ускоряет фильтрацию rental по customer_id",
        },
        {
            "table_name": "film",
            "column_names": "rental_rate",
            "index_type": "btree",
            "description": "Дополнительный индекс для смешанной нагрузки",
        },
    ],
    "mixed_heavy": [
        {
            "table_name": "film_category",
            "column_names": "film_id",
            "index_type": "btree",
            "description": "Ускоряет JOIN между film и film_category",
        },
        {
            "table_name": "rental",
            "column_names": "customer_id",
            "index_type": "btree",
            "description": "Ускоряет фильтрацию rental по customer_id",
        },
        {
            "table_name": "film",
            "column_names": "rental_rate",
            "index_type": "btree",
            "description": "Дополнительный индекс для смешанной нагрузки",
        },
        {
            "table_name": "customer",
            "column_names": "last_update",
            "index_type": "btree",
            "description": "Дополнительный индекс для heavy-нагрузки",
        },
    ],
    "oltp": [
        {
            "table_name": "inventory",
            "column_names": "film_id,store_id",
            "index_type": "btree",
            "description": "Композитный индекс для OLTP-сценария",
        },
    ],
    "olap": [
        {
            "table_name": "rental",
            "column_names": "rental_date",
            "index_type": "btree",
            "description": "Ускоряет фильтрацию по rental_date",
        },
        {
            "table_name": "payment",
            "column_names": "rental_id,amount",
            "index_type": "btree",
            "description": "Ускоряет JOIN и агрегацию по payment",
        },
        {
            "table_name": "film_category",
            "column_names": "category_id,film_id",
            "index_type": "btree",
            "description": "Ускоряет аналитический JOIN по категориям",
        },
    ],
}


def _make_index_name(scenario_name: str, table_name: str, column_names: str) -> str:
    suffix = column_names.replace(",", "_").replace(" ", "")
    name = f"idx_scenario_{scenario_name}_{table_name}_{suffix}"
    return name[:255]


def _seed_builtin_indexes(conn) -> None:
    existing = conn.execute(sa.text("SELECT COUNT(*) FROM scenario_indexes")).scalar()
    if existing and existing > 0:
        return

    scenarios = conn.execute(
        sa.text("SELECT id, name FROM test_scenarios WHERE is_builtin = 't'")
    ).fetchall()
    scenario_map = {row[1]: row[0] for row in scenarios}

    for scenario_name, indexes in BUILTIN_SCENARIO_INDEXES.items():
        scenario_id = scenario_map.get(scenario_name)
        if not scenario_id:
            continue

        for index_data in indexes:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO scenario_indexes (
                        id, scenario_id, table_name, column_names, index_type,
                        index_name, is_unique, condition, description
                    ) VALUES (
                        :id, :scenario_id, :table_name, :column_names, :index_type,
                        :index_name, 'f', NULL, :description
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "scenario_id": scenario_id,
                    "table_name": index_data["table_name"],
                    "column_names": index_data["column_names"],
                    "index_type": index_data.get("index_type", "btree"),
                    "index_name": _make_index_name(
                        scenario_name,
                        index_data["table_name"],
                        index_data["column_names"],
                    ),
                    "description": index_data.get("description"),
                },
            )


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scenario_indexes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scenario_id UUID NOT NULL REFERENCES test_scenarios(id) ON DELETE CASCADE,
            table_name VARCHAR(100) NOT NULL,
            column_names VARCHAR(500) NOT NULL,
            index_type VARCHAR(50) NOT NULL DEFAULT 'btree',
            index_name VARCHAR(255),
            is_unique VARCHAR(1) NOT NULL DEFAULT 'f',
            condition TEXT,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_indexes_scenario_id ON scenario_indexes(scenario_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_scenario_indexes_table_name ON scenario_indexes(table_name)"))

    _seed_builtin_indexes(conn)


def downgrade() -> None:
    op.drop_table("scenario_indexes")
