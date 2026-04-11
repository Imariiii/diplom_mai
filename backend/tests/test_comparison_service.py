"""
Интеграционные тесты для backend/comparison/service.py
Проверка ComparisonService.analyze с мокнутым repository,
определения ComparisonType, валидации и предупреждений.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.comparison.schemas import ComparisonType
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
    """Build a dict matching the shape returned by TestRepository.get_test_run_with_results."""
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
    """Build a list of raw metric sample dicts for request_latency + throughput_window."""
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


# ---------------------------------------------------------------------------
# Fixture: mock repository
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.get_time_series = AsyncMock(return_value=[])
    return repo


# ---------------------------------------------------------------------------
# _detect_comparison_type (no DB needed)
# ---------------------------------------------------------------------------

class TestDetectComparisonType:
    def _service(self):
        return ComparisonService(repository=AsyncMock())

    def test_cross_database(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "MySQL", db_keys=["conn_mysql"]),
            _make_test_data(id2, "PG", db_keys=["conn_pg"]),
        ]
        ct = svc._detect_comparison_type(tests)
        assert ct == ComparisonType.CROSS_DATABASE

    def test_scalability(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "4VU", virtual_users=4, db_keys=["conn_pg"]),
            _make_test_data(id2, "8VU", virtual_users=8, db_keys=["conn_pg"]),
        ]
        ct = svc._detect_comparison_type(tests)
        assert ct == ComparisonType.SCALABILITY

    def test_temporal(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "Run1", db_keys=["conn_pg"], created_at="2025-01-01T00:00:00Z"),
            _make_test_data(id2, "Run2", db_keys=["conn_pg"], created_at="2025-02-01T00:00:00Z"),
        ]
        ct = svc._detect_comparison_type(tests)
        assert ct == ComparisonType.TEMPORAL

    def test_mixed(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_mysql", "conn_pg"]),
            _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_mysql"]),
        ]
        ct = svc._detect_comparison_type(tests)
        assert ct == ComparisonType.MIXED


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

    def test_different_scenario_template_raises(self):
        svc = ComparisonService(repository=AsyncMock())
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", scenario_template_id="tmpl1"),
            _make_test_data(id2, "B", scenario_template_id="tmpl2"),
        ]
        with pytest.raises(ValueError, match="один и тот же сценарий"):
            svc._validate_tests_for_comparison(tests)


# ---------------------------------------------------------------------------
# Full analyze with mocked repository
# ---------------------------------------------------------------------------

class TestAnalyze:
    @pytest.mark.asyncio
    async def test_cross_database_analyze(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "MySQL", db_keys=["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_mysql", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(
            side_effect=lambda tid: test_data.get(tid)
        )
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid: samples.get(tid, [])
        )

        svc = ComparisonService(repository=mock_repo)
        result = await svc.analyze([id1, id2])

        assert result.comparison_type == ComparisonType.CROSS_DATABASE
        assert result.baseline_id == id1
        assert len(result.tests) == 2
        assert str(id1) in result.descriptive_stats
        assert str(id2) in result.descriptive_stats
        assert result.analysis_report is not None
        assert len(result.analysis_report.sections) > 0

    @pytest.mark.asyncio
    async def test_temporal_analyze(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "Jan", db_keys=["conn_pg"], created_at="2025-01-01T00:00:00Z"),
            str(id2): _make_test_data(id2, "Feb", db_keys=["conn_pg"], created_at="2025-02-01T00:00:00Z"),
        }
        samples = {
            str(id1): _make_metric_samples("conn_pg", seed=10),
            str(id2): _make_metric_samples("conn_pg", seed=20),
        }
        mock_repo.get_test_run_with_results = AsyncMock(
            side_effect=lambda tid: test_data.get(tid)
        )
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid: samples.get(tid, [])
        )

        svc = ComparisonService(repository=mock_repo)
        result = await svc.analyze([id1, id2])

        assert result.comparison_type == ComparisonType.TEMPORAL
        assert len(result.pairwise_comparisons) > 0

    @pytest.mark.asyncio
    async def test_explicit_baseline(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "A", db_keys=["conn_mysql"]),
            str(id2): _make_test_data(id2, "B", db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_mysql", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(
            side_effect=lambda tid: test_data.get(tid)
        )
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid: samples.get(tid, [])
        )

        svc = ComparisonService(repository=mock_repo)
        result = await svc.analyze([id1, id2], baseline_id=id2)
        assert result.baseline_id == id2

    @pytest.mark.asyncio
    async def test_charts_data_populated(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "MySQL", db_keys=["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_mysql", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(
            side_effect=lambda tid: test_data.get(tid)
        )
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid: samples.get(tid, [])
        )

        svc = ComparisonService(repository=mock_repo)
        result = await svc.analyze([id1, id2])

        assert len(result.charts_data.bar_chart) > 0
        assert len(result.charts_data.box_plot) > 0

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mock_repo):
        mock_repo.get_test_run_with_results = AsyncMock(return_value=None)
        svc = ComparisonService(repository=mock_repo)
        with pytest.raises(ValueError, match="не найден"):
            await svc.analyze([uuid.uuid4(), uuid.uuid4()])

    @pytest.mark.asyncio
    async def test_scalability_normalized_metrics(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        test_data = {
            str(id1): _make_test_data(id1, "4VU", virtual_users=4, db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "8VU", virtual_users=8, db_keys=["conn_pg"]),
        }
        samples = {
            str(id1): _make_metric_samples("conn_pg", seed=42),
            str(id2): _make_metric_samples("conn_pg", seed=99),
        }
        mock_repo.get_test_run_with_results = AsyncMock(
            side_effect=lambda tid: test_data.get(tid)
        )
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid: samples.get(tid, [])
        )

        svc = ComparisonService(repository=mock_repo)
        result = await svc.analyze([id1, id2])

        assert result.comparison_type == ComparisonType.SCALABILITY
        assert str(id1) in result.normalized_metrics or str(id2) in result.normalized_metrics
