"""
Ручные transaction-bundle для шаблона OLTP (Sakila и Brazilian E-com).

Автогенератор сценариев не используется: payload задаётся явно и версионируется
через MANUAL_OLTP_GENERATION_SOURCE.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa

from backend.database.logical_scenarios import MANUAL_OLTP_GENERATION_SOURCE, MANUAL_OLTP_TEMPLATE_ID


SAKILA_GROUP_NAMES = {"sakila"}
OLIST_GROUP_NAMES = {"brazilian e-com"}

SAKILA_PROFILE_PREFIX = "sakila_like"
OLIST_PROFILE_PREFIX = "olist_like"


def is_sakila_profile(profile_name: str, database_group_name: Optional[str] = None) -> bool:
    """Профиль или группа относится к схеме Sakila."""
    normalized_profile = (profile_name or "").lower()
    normalized_group = (database_group_name or "").lower()
    if normalized_profile.startswith(SAKILA_PROFILE_PREFIX):
        return True
    return normalized_group in SAKILA_GROUP_NAMES


def is_olist_profile(profile_name: str, database_group_name: Optional[str] = None) -> bool:
    """Профиль или группа относится к Brazilian E-com / Olist."""
    normalized_profile = (profile_name or "").lower()
    normalized_group = (database_group_name or "").lower()
    if normalized_profile.startswith(OLIST_PROFILE_PREFIX):
        return True
    return normalized_group in OLIST_GROUP_NAMES


def build_oltp_bundle_name(template_id: str, scope_name: str, variant: str = "common") -> str:
    """Имя bundle: oltp::<scope>::common|canonical."""
    return f"{template_id}::{scope_name}::{variant}"


def _param(
    param_name: str,
    table_ref: str,
    column_ref: str,
) -> Dict[str, Any]:
    return {
        "param_name": param_name,
        "param_type": "random_from_table",
        "table_ref": table_ref,
        "column_ref": column_ref,
    }


SAKILA_OLTP_TRANSACTIONS: List[Dict[str, Any]] = [
    {
        "name": "film_availability",
        "weight": 40,
        "order_index": 0,
        "description": "Просмотр каталога: фильм и доступные копии на складе.",
        "params": [_param("film_id", "film", "film_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT film_id, title, rental_rate FROM film "
                    "WHERE film_id = {film_id}"
                ),
                "query_type": "select",
                "order_index": 0,
                "description": "Карточка фильма по PK",
            },
            {
                "sql_template": (
                    "SELECT inventory_id, film_id, store_id FROM inventory "
                    "WHERE film_id = {film_id} LIMIT 5"
                ),
                "query_type": "select",
                "order_index": 1,
                "description": "Копии фильма в inventory",
            },
        ],
    },
    {
        "name": "customer_touch",
        "weight": 35,
        "order_index": 1,
        "description": "Чтение клиента и обновление last_update в одной транзакции.",
        "params": [_param("customer_id", "customer", "customer_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT customer_id, first_name, last_name, active FROM customer "
                    "WHERE customer_id = {customer_id}"
                ),
                "query_type": "select",
                "order_index": 0,
            },
            {
                "sql_template": (
                    "UPDATE customer SET last_update = NOW() "
                    "WHERE customer_id = {customer_id}"
                ),
                "query_type": "update",
                "order_index": 1,
            },
        ],
    },
    {
        "name": "rental_touch",
        "weight": 25,
        "order_index": 2,
        "description": "Просмотр аренды и обновление last_update по PK (без INSERT в composite UNIQUE).",
        "params": [_param("rental_id", "rental", "rental_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT rental_id, inventory_id, customer_id, rental_date "
                    "FROM rental WHERE rental_id = {rental_id}"
                ),
                "query_type": "select",
                "order_index": 0,
            },
            {
                "sql_template": (
                    "SELECT inventory_id, film_id, store_id FROM inventory "
                    "WHERE inventory_id = (SELECT inventory_id FROM rental WHERE rental_id = {rental_id})"
                ),
                "query_type": "select",
                "order_index": 1,
            },
            {
                "sql_template": (
                    "UPDATE rental SET last_update = NOW() WHERE rental_id = {rental_id}"
                ),
                "query_type": "update",
                "order_index": 2,
            },
        ],
    },
]

SAKILA_OLTP_INDEXES: List[Dict[str, Any]] = [
    {
        "table_name": "inventory",
        "column_names": "film_id,store_id",
        "index_type": "btree",
        "index_name": "idx_bundle_oltp_inventory_film_id_store_id",
        "description": "Композитный индекс для OLTP film/inventory",
    },
]

OLIST_OLTP_TRANSACTIONS: List[Dict[str, Any]] = [
    {
        "name": "order_lookup",
        "weight": 40,
        "order_index": 0,
        "description": "Заказ, позиции и клиент в одной транзакции.",
        "params": [_param("order_id", "olist_orders_dataset", "order_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT order_id, customer_id, order_status FROM olist_orders_dataset "
                    "WHERE order_id = '{order_id}'"
                ),
                "query_type": "select",
                "order_index": 0,
            },
            {
                "sql_template": (
                    "SELECT order_id, product_id, price FROM olist_order_items_dataset "
                    "WHERE order_id = '{order_id}' LIMIT 20"
                ),
                "query_type": "select",
                "order_index": 1,
            },
            {
                "sql_template": (
                    "SELECT a.order_id, b.customer_id, b.customer_city "
                    "FROM olist_orders_dataset a "
                    "JOIN olist_customers_dataset b ON a.customer_id = b.customer_id "
                    "WHERE a.order_id = '{order_id}'"
                ),
                "query_type": "select",
                "order_index": 2,
            },
        ],
    },
    {
        "name": "order_status_touch",
        "weight": 35,
        "order_index": 1,
        "description": "Чтение заказа и безопасный UPDATE статуса (no-op для restore).",
        "params": [_param("order_id", "olist_orders_dataset", "order_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT order_id, customer_id, order_status FROM olist_orders_dataset "
                    "WHERE order_id = '{order_id}'"
                ),
                "query_type": "select",
                "order_index": 0,
            },
            {
                "sql_template": (
                    "UPDATE olist_orders_dataset SET order_status = order_status "
                    "WHERE order_id = '{order_id}'"
                ),
                "query_type": "update",
                "order_index": 1,
            },
        ],
    },
    {
        "name": "customer_orders",
        "weight": 25,
        "order_index": 2,
        "description": "Профиль клиента и список его заказов.",
        "params": [_param("customer_id", "olist_customers_dataset", "customer_id")],
        "steps": [
            {
                "sql_template": (
                    "SELECT customer_id, customer_unique_id, customer_city "
                    "FROM olist_customers_dataset WHERE customer_id = '{customer_id}'"
                ),
                "query_type": "select",
                "order_index": 0,
            },
            {
                "sql_template": (
                    "SELECT order_id, order_status FROM olist_orders_dataset "
                    "WHERE customer_id = '{customer_id}' ORDER BY order_id LIMIT 10"
                ),
                "query_type": "select",
                "order_index": 1,
            },
        ],
    },
]

OLIST_OLTP_INDEXES: List[Dict[str, Any]] = [
    {
        "table_name": "olist_orders_dataset",
        "column_names": "customer_id",
        "index_type": "btree",
        "index_name": "idx_bundle_oltp_olist_orders_dataset_customer_id",
        "description": "Ускоряет JOIN orders → customers",
    },
]


def get_oltp_seed_for_profile(
    profile_name: str,
    database_group_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Вернуть payload транзакций и индексов для профиля Sakila или Olist."""
    if is_sakila_profile(profile_name, database_group_name):
        return {
            "transactions": SAKILA_OLTP_TRANSACTIONS,
            "indexes": SAKILA_OLTP_INDEXES,
        }
    if is_olist_profile(profile_name, database_group_name):
        return {
            "transactions": OLIST_OLTP_TRANSACTIONS,
            "indexes": OLIST_OLTP_INDEXES,
        }
    return None


def build_manual_oltp_bundle_payload(
    profile_name: str,
    scope_name: str,
    variant: str = "common",
    database_group_name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Собрать полный payload для upsert manual OLTP bundle."""
    seed = get_oltp_seed_for_profile(profile_name, database_group_name)
    if not seed:
        return None
    default_description = (
        f"Ручной OLTP transaction-bundle для {scope_name} "
        f"({MANUAL_OLTP_GENERATION_SOURCE})"
    )
    return {
        "scenario_template_id": MANUAL_OLTP_TEMPLATE_ID,
        "name": build_oltp_bundle_name(MANUAL_OLTP_TEMPLATE_ID, scope_name, variant),
        "description": description or default_description,
        "generation_source": MANUAL_OLTP_GENERATION_SOURCE,
        "workload_mode": "transaction",
        "queries": [],
        "transactions": seed["transactions"],
        "indexes": seed["indexes"],
    }


def _resolve_seed_for_bundle(profile_name: str, bundle_name: str) -> Optional[Dict[str, Any]]:
    """Определить seed по имени профиля или bundle."""
    if is_sakila_profile(profile_name, bundle_name):
        return {
            "transactions": SAKILA_OLTP_TRANSACTIONS,
            "indexes": SAKILA_OLTP_INDEXES,
        }
    if is_olist_profile(profile_name, bundle_name):
        return {
            "transactions": OLIST_OLTP_TRANSACTIONS,
            "indexes": OLIST_OLTP_INDEXES,
        }
    return None


def _clear_bundle_contents(conn, bundle_id: str) -> None:
    """Удалить queries/transactions/indexes bundle перед повторным seed."""
    conn.execute(
        sa.text(
            """
            DELETE FROM scenario_bundle_params
            WHERE query_id IN (
                SELECT id FROM scenario_bundle_queries WHERE bundle_id = :bundle_id
            )
            """
        ),
        {"bundle_id": bundle_id},
    )
    conn.execute(
        sa.text("DELETE FROM scenario_bundle_queries WHERE bundle_id = :bundle_id"),
        {"bundle_id": bundle_id},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM scenario_bundle_transaction_params
            WHERE transaction_id IN (
                SELECT id FROM scenario_bundle_transactions WHERE bundle_id = :bundle_id
            )
            """
        ),
        {"bundle_id": bundle_id},
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM scenario_bundle_transaction_steps
            WHERE transaction_id IN (
                SELECT id FROM scenario_bundle_transactions WHERE bundle_id = :bundle_id
            )
            """
        ),
        {"bundle_id": bundle_id},
    )
    conn.execute(
        sa.text("DELETE FROM scenario_bundle_transactions WHERE bundle_id = :bundle_id"),
        {"bundle_id": bundle_id},
    )
    conn.execute(
        sa.text("DELETE FROM scenario_bundle_indexes WHERE bundle_id = :bundle_id"),
        {"bundle_id": bundle_id},
    )


def _insert_transaction_bundle_contents(
    conn,
    bundle_id: str,
    seed: Dict[str, Any],
) -> None:
    """Вставить transactions, steps, params и indexes для bundle."""
    now = datetime.now(timezone.utc)
    for transaction in seed["transactions"]:
        transaction_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO scenario_bundle_transactions (
                    id, bundle_id, name, weight, order_index, description, created_at
                ) VALUES (
                    :id, :bundle_id, :name, :weight, :order_index, :description, :created_at
                )
                """
            ),
            {
                "id": transaction_id,
                "bundle_id": bundle_id,
                "name": transaction["name"],
                "weight": transaction.get("weight", 1),
                "order_index": transaction.get("order_index", 0),
                "description": transaction.get("description"),
                "created_at": now,
            },
        )
        for param in transaction.get("params", []):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO scenario_bundle_transaction_params (
                        id, transaction_id, param_name, param_type,
                        min_value, max_value, string_pattern, string_length,
                        table_ref, column_ref, current_value, step, created_at
                    ) VALUES (
                        :id, :transaction_id, :param_name, :param_type,
                        :min_value, :max_value, :string_pattern, :string_length,
                        :table_ref, :column_ref, :current_value, :step, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "transaction_id": transaction_id,
                    "param_name": param["param_name"],
                    "param_type": param["param_type"],
                    "min_value": param.get("min_value"),
                    "max_value": param.get("max_value"),
                    "string_pattern": param.get("string_pattern"),
                    "string_length": param.get("string_length"),
                    "table_ref": param.get("table_ref"),
                    "column_ref": param.get("column_ref"),
                    "current_value": param.get("current_value", 0),
                    "step": param.get("step", 1),
                    "created_at": now,
                },
            )
        for step in transaction.get("steps", []):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO scenario_bundle_transaction_steps (
                        id, transaction_id, sql_template, query_type,
                        order_index, description, created_at
                    ) VALUES (
                        :id, :transaction_id, :sql_template, :query_type,
                        :order_index, :description, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "transaction_id": transaction_id,
                    "sql_template": step["sql_template"],
                    "query_type": step["query_type"],
                    "order_index": step.get("order_index", 0),
                    "description": step.get("description"),
                    "created_at": now,
                },
            )

    for index_def in seed.get("indexes", []):
        conn.execute(
            sa.text(
                """
                INSERT INTO scenario_bundle_indexes (
                    id, bundle_id, table_name, column_names, index_type,
                    index_name, is_unique, condition, description, created_at
                ) VALUES (
                    :id, :bundle_id, :table_name, :column_names, :index_type,
                    :index_name, :is_unique, :condition, :description, :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "bundle_id": bundle_id,
                "table_name": index_def["table_name"],
                "column_names": index_def["column_names"],
                "index_type": index_def.get("index_type", "btree"),
                "index_name": index_def.get("index_name"),
                "is_unique": "t" if index_def.get("is_unique") else "f",
                "condition": index_def.get("condition"),
                "description": index_def.get("description"),
                "created_at": now,
            },
        )


def apply_oltp_transaction_migration(conn) -> None:
    """Синхронно перевести существующие OLTP bundle в transaction mode (Alembic)."""
    conn.execute(
        sa.text(
            "UPDATE scenario_templates SET is_builtin = 'f', updated_at = now() "
            "WHERE id = :template_id"
        ),
        {"template_id": MANUAL_OLTP_TEMPLATE_ID},
    )

    rows = conn.execute(
        sa.text(
            """
            SELECT sb.id::text AS bundle_id,
                   sb.name AS bundle_name,
                   sb.generation_source AS generation_source,
                   sp.name AS profile_name
            FROM scenario_bundles sb
            JOIN schema_profiles sp ON sp.id = sb.schema_profile_id
            WHERE sb.scenario_template_id = :template_id
            """
        ),
        {"template_id": MANUAL_OLTP_TEMPLATE_ID},
    ).mappings().all()

    for row in rows:
        if row["generation_source"] == "manual_variant":
            continue
        seed = _resolve_seed_for_bundle(row["profile_name"], row["bundle_name"])
        if not seed:
            continue
        bundle_id = row["bundle_id"]
        _clear_bundle_contents(conn, bundle_id)
        conn.execute(
            sa.text(
                """
                UPDATE scenario_bundles
                SET workload_mode = 'transaction',
                    is_builtin = 'f',
                    generation_source = :generation_source,
                    updated_at = now()
                WHERE id = :bundle_id
                """
            ),
            {
                "bundle_id": bundle_id,
                "generation_source": MANUAL_OLTP_GENERATION_SOURCE,
            },
        )
        _insert_transaction_bundle_contents(conn, bundle_id, seed)
