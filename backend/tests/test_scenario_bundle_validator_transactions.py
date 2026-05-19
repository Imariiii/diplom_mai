"""Тесты валидации transaction bundle."""
import pytest

from backend.database.scenario_bundle_validator import ScenarioBundleValidator


@pytest.mark.asyncio
async def test_transaction_bundle_rejects_explicit_tx_control():
    validator = ScenarioBundleValidator(connection_repository=None)
    bundle = {
        "workload_mode": "transaction",
        "transactions": [
            {
                "name": "bad",
                "steps": [
                    {"sql_template": "BEGIN; SELECT 1", "query_type": "select"},
                ],
                "params": [],
            },
        ],
    }
    errors, warnings = await validator._validate_transaction_bundle_for_connection(
        bundle=bundle,
        connection_id="c1",
        connection_name="test",
        dbms_type="postgresql",
        metadata=type("Meta", (), {"tables": {}})(),
    )
    assert any("BEGIN" in error for error in errors)
    assert warnings == []


@pytest.mark.asyncio
async def test_transaction_bundle_rejects_duplicate_param_names():
    validator = ScenarioBundleValidator(connection_repository=None)
    bundle = {
        "workload_mode": "transaction",
        "transactions": [
            {
                "name": "dup",
                "steps": [{"sql_template": "SELECT {id}", "query_type": "select"}],
                "params": [
                    {"param_name": "id", "param_type": "random_int"},
                    {"param_name": "id", "param_type": "random_int"},
                ],
            },
        ],
    }
    errors, _ = await validator._validate_transaction_bundle_for_connection(
        bundle=bundle,
        connection_id="c1",
        connection_name="test",
        dbms_type="postgresql",
        metadata=type("Meta", (), {"tables": {}})(),
    )
    assert any("дублирующиеся param_name" in error for error in errors)
