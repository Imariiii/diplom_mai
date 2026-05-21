"""Тесты исключения OLTP из автогенерации bundle."""
from types import SimpleNamespace

from backend.database.logical_scenarios import MANUAL_OLTP_TEMPLATE_ID
from backend.database.logical_scenario_bootstrap import LogicalScenarioBootstrap


def test_is_bundle_complete_transaction_mode():
    bootstrap = LogicalScenarioBootstrap(
        connection_repository=None,
        profile_repository=None,
        bundle_repository=None,
    )
    bundle = SimpleNamespace(
        workload_mode="transaction",
        queries=[],
        indexes=[],
        transactions=[SimpleNamespace(steps=[SimpleNamespace()])],
    )
    assert bootstrap._is_bundle_complete(bundle) is True


def test_is_bundle_complete_transaction_without_steps():
    bootstrap = LogicalScenarioBootstrap(
        connection_repository=None,
        profile_repository=None,
        bundle_repository=None,
    )
    bundle = SimpleNamespace(
        workload_mode="transaction",
        queries=[],
        indexes=[],
        transactions=[SimpleNamespace(steps=[])],
    )
    assert bootstrap._is_bundle_complete(bundle) is False


def test_missing_templates_only_considers_auto_generated():
    """Bootstrap auto-gen не требует OLTP bundle (он вне списка templates)."""
    bootstrap = LogicalScenarioBootstrap(
        connection_repository=None,
        profile_repository=None,
        bundle_repository=None,
    )
    templates = [SimpleNamespace(id="read_only")]
    existing_bundles = [
        SimpleNamespace(
            scenario_template_id="read_only",
            is_builtin="t",
            workload_mode="query",
            queries=[SimpleNamespace()],
            indexes=[SimpleNamespace()],
            transactions=[],
            generation_source="logical-scenario-generator-v9",
            name="read_only::Sakila::common",
            generated_from_connection_id="conn-1",
        ),
    ]
    missing = bootstrap._missing_or_incomplete_template_ids(
        templates=templates,
        existing_bundles=existing_bundles,
        expected_name_builder=lambda template_id: f"{template_id}::Sakila::common",
        reference_connection_id="conn-1",
    )
    assert missing == []
    assert MANUAL_OLTP_TEMPLATE_ID not in [template.id for template in templates]
