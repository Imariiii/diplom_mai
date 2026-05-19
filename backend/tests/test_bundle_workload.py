"""Тесты вспомогательных функций workload bundle."""
from backend.database.bundle_workload import (
    collect_bundle_sql_templates,
    collect_param_refs_for_cache,
    get_bundle_workload_mode,
    get_primary_rate_unit,
)


def test_get_bundle_workload_mode_defaults_to_query():
    assert get_bundle_workload_mode({}) == "query"
    assert get_bundle_workload_mode({"workload_mode": "transaction"}) == "transaction"
    assert get_bundle_workload_mode({"workload_mode": "unknown"}) == "query"


def test_get_primary_rate_unit():
    assert get_primary_rate_unit("query") == "qps"
    assert get_primary_rate_unit("transaction") == "tps"


def test_collect_bundle_sql_templates_transaction_mode():
    bundle = {
        "workload_mode": "transaction",
        "transactions": [
            {
                "steps": [
                    {"sql_template": "SELECT 1"},
                    {"sql_template": "UPDATE t SET x=1"},
                ],
            },
        ],
    }
    assert collect_bundle_sql_templates(bundle) == ["SELECT 1", "UPDATE t SET x=1"]


def test_collect_param_refs_for_cache_transaction_mode():
    bundle = {
        "workload_mode": "transaction",
        "transactions": [{"params": [{"param_name": "id", "param_type": "random_int"}]}],
    }
    refs = collect_param_refs_for_cache(bundle)
    assert refs == [{"param_name": "id", "param_type": "random_int"}]
