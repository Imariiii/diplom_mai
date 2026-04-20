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


def _make_throughput_samples(
    db_key: str,
    batch_values: Optional[List[float]] = None,
    realtime_values: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Build throughput samples for source-priority checks."""
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
# _detect_comparison_type (no DB needed)
# ---------------------------------------------------------------------------

class TestDetectTraits:
    def _service(self):
        return ComparisonService(repository=AsyncMock())

    def test_cross_database(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "MySQL", db_keys=["conn_mysql"]),
            _make_test_data(id2, "PG", db_keys=["conn_pg"]),
        ]
        traits = svc._detect_traits(tests)
        assert traits.multiple_dbs
        assert traits.same_load_params
        ct = svc._derive_comparison_type(traits)
        assert ct == ComparisonType.CROSS_DATABASE

    def test_scalability(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "4VU", virtual_users=4, db_keys=["conn_pg"]),
            _make_test_data(id2, "8VU", virtual_users=8, db_keys=["conn_pg"]),
        ]
        traits = svc._detect_traits(tests)
        assert traits.diff_virtual_users
        assert not traits.multiple_dbs
        ct = svc._derive_comparison_type(traits)
        assert ct == ComparisonType.SCALABILITY

    def test_temporal(self):
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "Run1", db_keys=["conn_pg"], created_at="2025-01-01T00:00:00Z"),
            _make_test_data(id2, "Run2", db_keys=["conn_pg"], created_at="2025-02-01T00:00:00Z"),
        ]
        traits = svc._detect_traits(tests)
        assert traits.is_temporal
        assert traits.same_load_params
        ct = svc._derive_comparison_type(traits)
        assert ct == ComparisonType.TEMPORAL

    def test_config_comparison_multi_db_diff_vu(self):
        """Same scenario, multiple DBs, different VU -> CONFIG_COMPARISON (was 'mixed')."""
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_mysql", "conn_pg"]),
            _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_mysql", "conn_pg"]),
        ]
        traits = svc._detect_traits(tests)
        assert traits.diff_virtual_users
        assert traits.multiple_dbs
        ct = svc._derive_comparison_type(traits)
        assert ct == ComparisonType.CONFIG_COMPARISON

    def test_same_scenario_diff_vu_single_db(self):
        """Same scenario, single DB, different VU -> SCALABILITY."""
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", virtual_users=10, db_keys=["conn_pg"]),
            _make_test_data(id2, "B", virtual_users=50, db_keys=["conn_pg"]),
        ]
        traits = svc._detect_traits(tests)
        assert traits.diff_virtual_users
        assert not traits.multiple_dbs
        ct = svc._derive_comparison_type(traits)
        assert ct == ComparisonType.SCALABILITY

    def test_diff_db_targets_subsets(self):
        """Tests with different DB subsets."""
        svc = self._service()
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_mysql", "conn_pg"]),
            _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_mysql"]),
        ]
        traits = svc._detect_traits(tests)
        assert not traits.same_db_targets
        assert traits.multiple_dbs
        assert traits.diff_virtual_users


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
        assert result.traits is not None
        assert result.traits.multiple_dbs
        assert result.traits.same_load_params
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
        assert result.traits is not None
        assert result.traits.is_temporal
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
        assert result.traits is not None
        assert result.traits.diff_virtual_users
        assert str(id1) in result.normalized_metrics or str(id2) in result.normalized_metrics
