"""
Тесты менеджера сценарных индексов.
"""
from backend.database.scenario_generator import ScenarioGenerator
from backend.load_tester.index_manager import IndexManager


def test_index_manager_shortens_existing_long_bundle_index_name():
    manager = IndexManager()
    index_def = {
        "table_name": "olist_customers_dataset",
        "column_names": "customer_zip_code_prefix",
        "index_name": "idx_bundle_mixed_light_olist_customers_dataset_customer_zip_code_prefix",
    }

    resolved = manager._resolve_index_name(index_def)

    assert len(resolved) <= 63
    assert resolved.startswith("idx_bundle_mixed_light_olist_customers")
    assert resolved != index_def["index_name"]


def test_scenario_generator_builds_cross_db_safe_index_names():
    generator = ScenarioGenerator()

    index_name = generator._build_index_name(
        "mixed_light",
        "olist_customers_dataset",
        "customer_zip_code_prefix",
    )

    assert len(index_name) <= 63
    assert index_name.startswith("idx_bundle_mixed_light_olist_customers")
