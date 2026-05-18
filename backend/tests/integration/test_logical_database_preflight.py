"""
Интеграционные preflight-тесты запуска logical database сценариев.
"""
import os
from typing import Iterable, List

import pytest
from sqlalchemy.exc import OperationalError

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.database.scenario_generator import DEFAULT_SCENARIO_TYPES


pytestmark = pytest.mark.integration

DEFAULT_HISTORY_URL = "postgresql+asyncpg://postgres:history123@localhost:5433/project_data"
DEFAULT_LOGICAL_DATABASES = ("Sakila", "Brazilian E-com")
DEFAULT_SCENARIOS = tuple(DEFAULT_SCENARIO_TYPES)
EXPECTED_DBMS_TYPES = {"postgresql", "mysql", "mariadb"}


def _split_env(name: str, default: Iterable[str]) -> List[str]:
    raw_value = os.getenv(name)
    if not raw_value:
        return list(default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _history_url() -> str:
    return (
        os.getenv("LOGICAL_PREFLIGHT_HISTORY_DATABASE_URL")
        or os.getenv("HISTORY_DATABASE_URL")
        or DEFAULT_HISTORY_URL
    )


@pytest.fixture(scope="module")
def preflight_enabled():
    if os.getenv("LOGICAL_PREFLIGHT_ENABLED") != "1":
        pytest.skip(
            "Preflight logical DB tests are opt-in. "
            "Set LOGICAL_PREFLIGHT_ENABLED=1 and load .env with ENCRYPTION_KEY."
        )


@pytest.fixture
async def repositories(preflight_enabled):
    history_url = _history_url()
    connection_repo = ConnectionRepository(history_url)
    logical_db_repo = LogicalDatabaseRepository(history_url)
    bundle_repo = ScenarioBundleRepository(history_url)
    try:
        yield connection_repo, logical_db_repo, bundle_repo
    except OperationalError as exc:
        pytest.skip(f"project_data is not available for logical DB preflight: {exc}")
    finally:
        await connection_repo.engine.dispose()
        await logical_db_repo.engine.dispose()
        await bundle_repo.engine.dispose()


@pytest.mark.parametrize("logical_db_name", _split_env("LOGICAL_PREFLIGHT_DATABASES", DEFAULT_LOGICAL_DATABASES))
@pytest.mark.parametrize("scenario_template_id", _split_env("LOGICAL_PREFLIGHT_SCENARIOS", DEFAULT_SCENARIOS))
async def test_logical_database_bundle_is_ready_for_load_test(
    repositories,
    logical_db_name: str,
    scenario_template_id: str,
):
    """Проверить путь запуска: logical DB -> active bundle -> SQL preflight."""
    connection_repo, logical_db_repo, bundle_repo = repositories
    logical_db = await logical_db_repo.get_by_name(logical_db_name)
    assert logical_db is not None, f"Logical database '{logical_db_name}' не найдена"
    assert logical_db.profile_status == "confirmed", (
        f"{logical_db_name}: profile_status={logical_db.profile_status}, нужен confirmed"
    )
    assert logical_db.compatibility_status != "invalid", (
        f"{logical_db_name}: compatibility_status={logical_db.compatibility_status}"
    )

    active_connections = [
        connection
        for connection in logical_db.connections
        if connection.is_active == "t"
    ]
    active_dbms_types = {connection.dbms_type for connection in active_connections}
    assert active_dbms_types == EXPECTED_DBMS_TYPES, (
        f"{logical_db_name}: ожидаются подключения PostgreSQL/MySQL/MariaDB, "
        f"получено {sorted(active_dbms_types)}"
    )
    pending_connections = [
        connection.name
        for connection in active_connections
        if connection.profile_source == "pending_review"
    ]
    assert not pending_connections, (
        f"{logical_db_name}: подключения ожидают подтверждения schema profile: "
        + ", ".join(pending_connections)
    )

    connection_ids = [str(connection.id) for connection in active_connections]
    resolver = ScenarioBundleResolver(connection_repo, bundle_repo)
    resolved = await resolver.resolve_for_connections(
        connection_ids=connection_ids,
        scenario_template_id=scenario_template_id,
    )

    bundle = resolved["bundle"]
    assert bundle["queries"], f"{logical_db_name}/{scenario_template_id}: bundle не содержит queries"
    if len(active_connections) >= 2:
        expected_common_name = f"{scenario_template_id}::{logical_db_name}::common"
        assert bundle.get("name") == expected_common_name, (
            f"{logical_db_name}/{scenario_template_id}: ожидался common bundle "
            f"'{expected_common_name}', получен '{bundle.get('name')}'"
        )

    validator = ScenarioBundleValidator(connection_repo)
    try:
        preflight = await validator.validate_bundle_for_connections(
            bundle=bundle,
            connection_ids=connection_ids,
        )
    finally:
        await validator.schema_analyzer.db_connection.close_all()
    assert preflight["valid"], (
        f"{logical_db_name}/{scenario_template_id}: bundle не готов к запуску: "
        + "; ".join(preflight.get("errors", []))
    )
