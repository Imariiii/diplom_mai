"""
Интеграционные тесты для backend/comparison/service.py
Проверка ComparisonService.analyze с мокнутым repository
для обоих режимов: per_test и series.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.comparison.schemas import AnalysisMode, ComparisonRequest
from backend.comparison.service import ComparisonService


# ---------------------------------------------------------------------------
# Helpers for building mock test data as it comes from the repository
# ---------------------------------------------------------------------------

def _make_test_data(
    test_id: uuid.UUID,
    name: str = "Test",
    virtual_users: int = 4,
    iterations: int = 100,
    scenario: str = "mixed_light",
    db_keys: Optional[List[str]] = None,
    logical_database_id: Optional[str] = None,
    scenario_template_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    db_keys = db_keys or ["conn_pg"]
    results = []
    for db_key in db_keys:
        results.append({
            "db_type": "postgresql",
            "query_id": "q1",
            "metrics": {
                "connection_key": db_key,
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
        "status": "completed",
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
        "logical_database_id": logical_database_id,
    }


def _make_metric_samples(db_key: str, n: int = 100, seed: int = 42) -> List[Dict[str, Any]]:
    rng = np.random.RandomState(seed)
    samples = []
    for i in range(n):
        samples.append({
            "sample_type": "request_latency",
            "connection_key": db_key,
            "latency_ms": float(rng.normal(45.0, 8.0)),
            "throughput": None,
            "tps": None,
            "is_error": False,
        })
    for i in range(20):
        samples.append({
            "sample_type": "throughput_window",
            "connection_key": db_key,
            "latency_ms": None,
            "throughput": float(rng.normal(120.0, 15.0)),
            "tps": None,
            "is_error": False,
        })
    return samples


def _make_throughput_samples(
    db_key: str,
    batch_values: Optional[List[float]] = None,
    realtime_values: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for value in batch_values or []:
        samples.append({
            "sample_type": "throughput_window",
            "connection_key": db_key,
            "latency_ms": None,
            "throughput": value,
            "tps": None,
            "is_error": False,
        })
    for value in realtime_values or []:
        samples.append({
            "sample_type": "throughput_realtime",
            "connection_key": db_key,
            "latency_ms": None,
            "throughput": value,
            "tps": None,
            "is_error": False,
        })
    return samples


# ---------------------------------------------------------------------------
# Fixture: mock repository
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.get_time_series = AsyncMock(return_value=[])
    return repo


# ---------------------------------------------------------------------------
# Throughput sample source priority
# ---------------------------------------------------------------------------

class TestThroughputSamplePriority:
    def _service(self):
        return ComparisonService(repository=AsyncMock())

    def test_extract_prefers_batch_windows_over_realtime(self):
        svc = self._service()
        samples = _make_throughput_samples(
            "conn_pg",
            batch_values=[100.0, 120.0],
            realtime_values=[900.0, 950.0],
        )
        assert svc._extract_throughput_values(samples) == [100.0, 120.0]

    def test_extract_falls_back_to_realtime(self):
        svc = self._service()
        samples = _make_throughput_samples(
            "conn_pg",
            batch_values=[],
            realtime_values=[80.0, 82.0, 85.0],
        )
        assert svc._extract_throughput_values(samples) == [80.0, 82.0, 85.0]

    @pytest.mark.asyncio
    async def test_build_series_from_metric_samples_uses_priority_source(self):
        repo = AsyncMock()
        repo.get_metric_samples = AsyncMock(return_value=_make_throughput_samples(
            "conn_pg",
            batch_values=[40.0, 45.0],
            realtime_values=[400.0, 450.0],
        ))
        svc = ComparisonService(repository=repo)
        series = await svc._build_series_from_metric_samples("test-id", "conn_pg")
        assert [point["throughput"] for point in series] == [40.0, 45.0]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_incomplete_test_raises(self):
        svc = ComparisonService(repository=AsyncMock())
        id1 = uuid.uuid4()
        tests = [_make_test_data(id1, "A")]
        tests[0]["status"] = "running"
        with pytest.raises(ValueError, match="не завершён"):
            svc._validate_tests_for_comparison(tests)

    def test_different_logical_db_raises(self):
        svc = ComparisonService(repository=AsyncMock())
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", logical_database_id="ldb1"),
            _make_test_data(id2, "B", logical_database_id="ldb2"),
        ]
        with pytest.raises(ValueError, match="одной логической"):
            svc._validate_tests_for_comparison(tests)

    def test_incomplete_test_status_raises(self):
        """Незавершённые прогоны отклоняются при валидации."""
        svc = ComparisonService(repository=AsyncMock())
        id1 = uuid.uuid4()
        tests = [_make_test_data(id1, "A")]
        tests[0]["status"] = "failed"
        with pytest.raises(ValueError, match="не завершён"):
            svc._validate_tests_for_comparison(tests)


# ---------------------------------------------------------------------------
# Per-test analyze
# ---------------------------------------------------------------------------

class TestPerTestAnalyze:
    @pytest.mark.asyncio
    async def test_per_test_single_run(self, mock_repo):
        id1 = uuid.uuid4()
        test_data = {str(id1): _make_test_data(id1, "MySQL+PG", db_keys=["conn_mysql", "conn_pg"])}
        samples = {str(id1): _make_metric_samples("conn_mysql", seed=42) + _make_metric_samples("conn_pg", seed=99)}
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        assert result.analysis_mode == "per_test"
        assert result.test.id == id1
        assert "conn_mysql" in result.descriptive_stats or "conn_pg" in result.descriptive_stats
        assert result.analysis_report is not None

    @pytest.mark.asyncio
    async def test_per_test_not_found_raises(self, mock_repo):
        mock_repo.get_test_run_with_results = AsyncMock(return_value=None)
        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[uuid.uuid4()])
        with pytest.raises(ValueError, match="не найден"):
            await svc.analyze(request)


# ---------------------------------------------------------------------------
# Series analyze
# ---------------------------------------------------------------------------

class TestSeriesAnalyze:
    @pytest.mark.asyncio
    async def test_series_two_tests(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "4VU", virtual_users=4, db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "8VU", virtual_users=8, db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_pg", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2], baseline_id=id1)
        result = await svc.analyze(request)

        assert result.analysis_mode == "series"
        assert len(result.tests) == 2
        assert result.baseline_id == id1
        assert result.comparability is not None
        assert len(result.load_levels) > 0
        assert result.analysis_report is not None

    @pytest.mark.asyncio
    async def test_series_explicit_baseline(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "A", db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "B", db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_pg", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2], baseline_id=id2)
        result = await svc.analyze(request)
        assert result.baseline_id == id2

    @pytest.mark.asyncio
    async def test_series_charts_populated(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "MySQL", db_keys=["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_mysql", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        result = await svc.analyze(request)

        assert result.charts is not None

    @pytest.mark.asyncio
    async def test_series_not_found_raises(self, mock_repo):
        mock_repo.get_test_run_with_results = AsyncMock(return_value=None)
        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[uuid.uuid4(), uuid.uuid4()])
        with pytest.raises(ValueError, match="не найден"):
            await svc.analyze(request)

    @pytest.mark.asyncio
    async def test_series_per_db_summary(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "4VU", virtual_users=4, db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "8VU", virtual_users=8, db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_pg", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2], baseline_id=id1)
        result = await svc.analyze(request)

        assert len(result.per_db) > 0
        for db_key, summary in result.per_db.items():
            assert summary.db_key == db_key
            assert summary.degradation is not None
