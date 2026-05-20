"""
Тесты корректности сравнения (fair comparison).
Проверяют, что система корректно валидирует сопоставимость тестов,
выбирает baseline, обрабатывает предупреждения.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.comparison.schemas import ComparisonRequest
from backend.comparison.service import ComparisonService


def _make_test_data(
    test_id, name="Test", virtual_users=4, iterations=100,
    scenario="mixed_light", db_keys=None,
    database_group_id=None, scenario_template_id=None,
    created_at=None, status="completed",
):
    db_keys = db_keys or ["conn_pg"]
    results = []
    for dk in db_keys:
        results.append({
            "db_type": "postgresql",
            "query_id": "q1",
            "metrics": {
                "connection_key": dk,
                "avg_response_time_ms": 45.0,
                "throughput": 120.0,
                "total_queries": iterations * virtual_users,
                "error_count": 0,
                "total_time_seconds": 60.0,
            },
        })
    return {
        "id": test_id,
        "name": name,
        "status": status,
        "config": {
            "virtual_users": virtual_users,
            "iterations": iterations,
            "scenario": scenario,
            "scenario_template_id": scenario_template_id,
            "db_types": [],
            "warmup_time": 0,
        },
        "results": results,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "database_group_id": database_group_id,
    }


def _make_samples(db_key, n=100, seed=42):
    rng = np.random.RandomState(seed)
    samples = []
    for _ in range(n):
        samples.append({
            "sample_type": "request_latency",
            "connection_key": db_key,
            "latency_ms": float(rng.normal(45.0, 8.0)),
        })
    for _ in range(20):
        samples.append({
            "sample_type": "throughput_window",
            "connection_key": db_key,
            "throughput": float(rng.normal(120.0, 15.0)),
        })
    return samples


def _mock_repo(test_data_map, samples_map=None):
    repo = AsyncMock()
    repo.get_test_run_with_results = AsyncMock(
        side_effect=lambda tid: test_data_map.get(tid)
    )
    repo.get_metric_samples = AsyncMock(
        side_effect=lambda tid: (samples_map or {}).get(tid, [])
    )
    repo.get_time_series = AsyncMock(return_value=[])
    return repo


# =========================================================================
# Baseline selection (series mode)
# =========================================================================

class TestBaselineSelection:
    @pytest.mark.asyncio
    async def test_default_baseline_is_first(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "B", db_keys=["conn_pg"]),
        }
        sm = {str(id1): _make_samples("conn_pg"), str(id2): _make_samples("conn_pg", seed=99)}
        svc = ComparisonService(repository=_mock_repo(td, sm))
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        result = await svc.analyze(request)
        assert result.baseline_id == id1

    @pytest.mark.asyncio
    async def test_explicit_baseline(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "B", db_keys=["conn_pg"]),
        }
        sm = {str(id1): _make_samples("conn_pg"), str(id2): _make_samples("conn_pg", seed=99)}
        svc = ComparisonService(repository=_mock_repo(td, sm))
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2], baseline_id=id2)
        result = await svc.analyze(request)
        assert result.baseline_id == id2

    @pytest.mark.asyncio
    async def test_baseline_not_in_list_raises(self):
        svc = ComparisonService(repository=AsyncMock())
        with pytest.raises(ValueError, match="Baseline"):
            svc._resolve_baseline_id([uuid.uuid4(), uuid.uuid4()], uuid.uuid4())


# =========================================================================
# Fair comparison warnings (series mode)
# =========================================================================

class TestFairComparisonWarnings:
    @pytest.mark.asyncio
    async def test_different_logical_db_rejected(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", database_group_id="ldb1", db_keys=["c1"]),
            str(id2): _make_test_data(id2, "B", database_group_id="ldb2", db_keys=["c1"]),
        }
        svc = ComparisonService(repository=_mock_repo(td))
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        with pytest.raises(ValueError, match="одной группе баз"):
            await svc.analyze(request)

    @pytest.mark.asyncio
    async def test_different_scenario_rejected(self):
        """Разные сценарии делают прогоны несопоставимыми для серийного анализа."""
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", scenario="mixed_light", db_keys=["c1"]),
            str(id2): _make_test_data(id2, "B", scenario="write_heavy", db_keys=["c1"]),
        }
        svc = ComparisonService(repository=_mock_repo(td))
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        with pytest.raises(ValueError, match="несопоставимы"):
            await svc.analyze(request)


# =========================================================================
# Multiple tests (2-5, series mode)
# =========================================================================

class TestMultipleTests:
    @pytest.mark.asyncio
    async def test_two_tests(self):
        ids = [uuid.uuid4() for _ in range(2)]
        td = {str(i): _make_test_data(i, f"T{n}", db_keys=["conn_pg"],
              created_at=f"2025-0{n+1}-01T00:00:00Z") for n, i in enumerate(ids)}
        sm = {str(i): _make_samples("conn_pg", seed=n*10) for n, i in enumerate(ids)}
        svc = ComparisonService(repository=_mock_repo(td, sm))
        request = ComparisonRequest(analysis_mode="series", test_ids=ids)
        result = await svc.analyze(request)
        assert len(result.tests) == 2

    @pytest.mark.asyncio
    async def test_three_tests(self):
        ids = [uuid.uuid4() for _ in range(3)]
        td = {str(i): _make_test_data(i, f"T{n}", db_keys=["conn_pg"],
              created_at=f"2025-0{n+1}-01T00:00:00Z") for n, i in enumerate(ids)}
        sm = {str(i): _make_samples("conn_pg", seed=n*10) for n, i in enumerate(ids)}
        svc = ComparisonService(repository=_mock_repo(td, sm))
        request = ComparisonRequest(analysis_mode="series", test_ids=ids)
        result = await svc.analyze(request)
        assert len(result.tests) == 3

    @pytest.mark.asyncio
    async def test_five_tests(self):
        ids = [uuid.uuid4() for _ in range(5)]
        td = {str(i): _make_test_data(i, f"T{n}", db_keys=["conn_pg"],
              created_at=f"2025-0{n+1}-01T00:00:00Z") for n, i in enumerate(ids)}
        sm = {str(i): _make_samples("conn_pg", seed=n*10) for n, i in enumerate(ids)}
        svc = ComparisonService(repository=_mock_repo(td, sm))
        request = ComparisonRequest(analysis_mode="series", test_ids=ids)
        result = await svc.analyze(request)
        assert len(result.tests) == 5


# =========================================================================
# Tests without raw samples (aggregate-only)
# =========================================================================

class TestAggregateOnlyData:
    @pytest.mark.asyncio
    async def test_no_raw_samples_still_works(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "B", db_keys=["conn_pg"]),
        }
        repo = _mock_repo(td, {})
        svc = ComparisonService(repository=repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        result = await svc.analyze(request)

        assert result is not None
        assert len(result.tests) == 2
