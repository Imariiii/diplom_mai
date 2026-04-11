"""
Интеграционные тесты API-роутов через httpx AsyncClient.
Мокаются глобальные репозитории из backend.initialize.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _test_run_dict(test_id: str, name: str = "Test") -> dict:
    return {
        "id": test_id,
        "name": name,
        "status": "completed",
        "config": {"virtual_users": 4, "iterations": 100, "scenario": "mixed_light"},
        "results": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "history_db" in data


# ---------------------------------------------------------------------------
# History routes
# ---------------------------------------------------------------------------

class TestHistoryRoutes:
    @pytest.mark.asyncio
    async def test_history_enabled(self, client):
        resp = await client.get("/history/enabled")
        assert resp.status_code == 200
        assert "enabled" in resp.json()

    @pytest.mark.asyncio
    async def test_get_tests_list(self, client):
        mock_repo = AsyncMock()
        mock_repo.get_all_test_runs = AsyncMock(return_value=[
            _test_run_dict("tid1", "Test1"),
        ])
        mock_repo.count_test_runs = AsyncMock(return_value=1)

        with patch("backend.api.routes.history_routes.get_test_repository", return_value=mock_repo):
            resp = await client.get("/history/tests")
        assert resp.status_code == 200
        body = resp.json()
        assert "tests" in body
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_get_single_test(self, client):
        tid = str(uuid.uuid4())
        mock_repo = AsyncMock()
        mock_repo.get_test_run_with_results = AsyncMock(return_value=_test_run_dict(tid))

        with patch("backend.api.routes.history_routes.get_test_repository", return_value=mock_repo):
            resp = await client.get(f"/history/tests/{tid}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_single_test_not_found(self, client):
        mock_repo = AsyncMock()
        mock_repo.get_test_run_with_results = AsyncMock(return_value=None)

        with patch("backend.api.routes.history_routes.get_test_repository", return_value=mock_repo):
            resp = await client.get(f"/history/tests/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_test(self, client):
        tid = str(uuid.uuid4())
        mock_repo = AsyncMock()
        mock_repo.delete_test_run = AsyncMock(return_value=True)

        with patch("backend.api.routes.history_routes.get_test_repository", return_value=mock_repo):
            resp = await client.delete(f"/history/tests/{tid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_test_not_found(self, client):
        mock_repo = AsyncMock()
        mock_repo.delete_test_run = AsyncMock(return_value=False)

        with patch("backend.api.routes.history_routes.get_test_repository", return_value=mock_repo):
            resp = await client.delete(f"/history/tests/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Comparison routes
# ---------------------------------------------------------------------------

class TestComparisonRoutes:
    @pytest.mark.asyncio
    async def test_invalid_request_422(self, client):
        with patch("backend.api.routes.comparison_routes.get_repositories",
                    return_value=(AsyncMock(), None, None)):
            resp = await client.post("/api/comparison/analyze", json={
                "test_ids": [str(uuid.uuid4())],
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_body_422(self, client):
        resp = await client.post("/api/comparison/analyze", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

class TestWebSocket:
    @pytest.mark.asyncio
    async def test_ws_connect_receives_connected(self):
        try:
            import httpx_ws
            from httpx_ws.transport import ASGIWebSocketTransport
        except ImportError:
            pytest.skip("httpx-ws not installed")
            return
        # Обычный ASGITransport не поднимает scope type=websocket — нужен транспорт из httpx-ws.
        async with ASGIWebSocketTransport(app=app) as transport:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                async with httpx_ws.aconnect_ws(f"/ws/test/{uuid.uuid4()}", ac) as ws:
                    msg = await ws.receive_json()
                    assert msg.get("type") == "connected"
