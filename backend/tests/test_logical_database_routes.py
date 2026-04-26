"""
Тесты API logical database для reference connection и compatibility state.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.api.routes.logical_database_routes import get_connection_repo, get_logical_db_repo


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _connection(connection_id="conn-1", name="PostgreSQL", is_active="t"):
    return SimpleNamespace(
        id=connection_id,
        name=name,
        dbms_type="postgresql",
        host="localhost",
        port=5432,
        database="pagila",
        group="local",
        schema_profile_id="profile-1",
        schema_profile=SimpleNamespace(name="profile"),
        detected_profile_name="profile",
        profile_confidence=0.9,
        profile_source="inherited",
        is_active=is_active,
    )


def _logical_db(connections=None):
    return SimpleNamespace(
        id="logical-1",
        name="Logical",
        description=None,
        schema_profile_id="profile-1",
        schema_profile=SimpleNamespace(name="profile"),
        reference_connection_id="conn-1",
        reference_connection=SimpleNamespace(name="PostgreSQL"),
        profile_status="confirmed",
        compatibility_status="unknown",
        compatibility_report=None,
        validated_at=None,
        created_at=None,
        updated_at=None,
        connections=connections or [_connection()],
    )


def _logical_db_with_status(profile_status="confirmed", compatibility_status="valid"):
    db = _logical_db()
    db.profile_status = profile_status
    db.compatibility_status = compatibility_status
    return db


class TestLogicalDatabaseRoutes:
    @pytest.mark.asyncio
    async def test_validate_uses_reference_and_updates_compatibility_state(self, client):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_logical_db())
        repo.update_profile_state = AsyncMock()

        async def fake_validate(self, connection_ids, reference_connection_id=None, mode="lenient"):
            assert connection_ids == ["conn-1"]
            assert reference_connection_id == "conn-1"
            assert mode == "strict"
            return {
                "valid": True,
                "errors": [],
                "warnings": [],
                "reference_connection_id": "conn-1",
                "reference_connection_name": "PostgreSQL",
                "mode": mode,
                "connections": [{"id": "conn-1", "name": "PostgreSQL", "dbms_type": "postgresql"}],
            }

        app.dependency_overrides[get_logical_db_repo] = lambda: repo
        app.dependency_overrides[get_connection_repo] = lambda: AsyncMock()
        with (
            patch(
                "backend.api.routes.logical_database_routes.LogicalDatabaseValidator.validate_connections",
                fake_validate,
            ),
        ):
            response = await client.get(
                "/api/logical-databases/logical-1/validate?reference_connection_id=conn-1&mode=strict"
            )

        assert response.status_code == 200
        assert response.json()["valid"] is True
        repo.update_profile_state.assert_awaited_once()
        assert repo.update_profile_state.await_args.kwargs["compatibility_status"] == "valid"

    @pytest.mark.asyncio
    async def test_reference_connection_must_belong_to_logical_database(self, client):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_logical_db(connections=[_connection("conn-1")]))

        app.dependency_overrides[get_logical_db_repo] = lambda: repo
        response = await client.put(
            "/api/logical-databases/logical-1/reference-connection",
            json={"reference_connection_id": "external"},
        )

        assert response.status_code == 400
        assert "reference_connection_id должен принадлежать" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_bundles_rejects_needs_review_state(self, client):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=_logical_db_with_status(profile_status="needs_review"))

        app.dependency_overrides[get_logical_db_repo] = lambda: repo
        response = await client.post(
            "/api/logical-databases/logical-1/bundles/generate",
            json={"scenario_template_ids": ["mixed_light"]},
        )

        assert response.status_code == 400
        assert "подтвердите профиль" in response.json()["detail"]
