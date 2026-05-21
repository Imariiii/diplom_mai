"""Тесты ручных OLTP transaction seeds."""
import re

from backend.database.logical_scenarios import (
    AUTO_GENERATED_SCENARIO_TEMPLATE_IDS,
    MANUAL_OLTP_GENERATION_SOURCE,
    MANUAL_OLTP_TEMPLATE_ID,
)
from backend.database.oltp_transaction_seeds import (
    OLIST_OLTP_TRANSACTIONS,
    SAKILA_OLTP_TRANSACTIONS,
    build_manual_oltp_bundle_payload,
    get_oltp_seed_for_profile,
    is_olist_profile,
    is_sakila_profile,
)

_TX_CONTROL_PATTERN = re.compile(r"\b(BEGIN|COMMIT|ROLLBACK)\b", re.IGNORECASE)


def _assert_transactions_valid(transactions):
    assert transactions
    total_weight = 0
    for transaction in transactions:
        assert transaction.get("weight", 0) > 0
        total_weight += transaction["weight"]
        steps = transaction.get("steps") or []
        assert steps
        param_names = [param["param_name"] for param in transaction.get("params", [])]
        assert len(param_names) == len(set(param_names))
        for step in steps:
            assert not _TX_CONTROL_PATTERN.search(step.get("sql_template", ""))


def test_oltp_not_in_auto_generated_templates():
    assert MANUAL_OLTP_TEMPLATE_ID not in AUTO_GENERATED_SCENARIO_TEMPLATE_IDS
    assert "read_only" in AUTO_GENERATED_SCENARIO_TEMPLATE_IDS


def test_profile_detection():
    assert is_sakila_profile("sakila_like_abc")
    assert is_sakila_profile("custom", "Sakila")
    assert is_olist_profile("olist_like_297bba88")
    assert is_olist_profile("custom", "Brazilian E-com")
    assert get_oltp_seed_for_profile("unknown_profile") is None


def test_sakila_and_olist_seed_structure():
    _assert_transactions_valid(SAKILA_OLTP_TRANSACTIONS)
    _assert_transactions_valid(OLIST_OLTP_TRANSACTIONS)

    sakila_payload = build_manual_oltp_bundle_payload(
        profile_name="sakila_like_test",
        scope_name="Sakila",
        variant="common",
    )
    assert sakila_payload is not None
    assert sakila_payload["workload_mode"] == "transaction"
    assert sakila_payload["generation_source"] == MANUAL_OLTP_GENERATION_SOURCE
    assert sakila_payload["queries"] == []
    assert len(sakila_payload["transactions"]) == 3
    rental_sql = " ".join(
        step["sql_template"]
        for tx in sakila_payload["transactions"]
        for step in tx["steps"]
    ).lower()
    assert "insert into rental" not in rental_sql

    ecom_payload = build_manual_oltp_bundle_payload(
        profile_name="olist_like_test",
        scope_name="Brazilian E-com",
        variant="common",
        database_group_name="Brazilian E-com",
    )
    assert ecom_payload is not None
    assert ecom_payload["workload_mode"] == "transaction"
    assert len(ecom_payload["transactions"]) == 3
    assert ecom_payload["indexes"]
