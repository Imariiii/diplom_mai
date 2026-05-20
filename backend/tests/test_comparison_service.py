"""
Интеграционные тесты для backend/comparison/service.py
Проверка ComparisonService.analyze с мокнутым repository
для обоих режимов: per_test и series.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.comparison.schemas import AnalysisMode, ComparisonRequest
from backend.comparison.service import ComparisonService
from backend.comparison.statistics import calculate_descriptive_stats


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
    database_group_id: Optional[str] = None,
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
        "database_group_id": database_group_id,
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

    def test_extract_ignores_realtime_without_batch_windows(self):
        """Realtime-сэмплы несут attempt_rate; сравнение throughput — только throughput_window."""
        svc = self._service()
        samples = _make_throughput_samples(
            "conn_pg",
            batch_values=[],
            realtime_values=[80.0, 82.0, 85.0],
        )
        assert svc._extract_throughput_values(samples) == []

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
            _make_test_data(id1, "A", database_group_id="ldb1"),
            _make_test_data(id2, "B", database_group_id="ldb2"),
        ]
        with pytest.raises(ValueError, match="одной группе баз"):
            svc._validate_tests_for_comparison(tests)

    def test_incomplete_test_status_raises(self):
        """Незавершённые прогоны отклоняются при валидации."""
        svc = ComparisonService(repository=AsyncMock())
        id1 = uuid.uuid4()
        tests = [_make_test_data(id1, "A")]
        tests[0]["status"] = "failed"
        with pytest.raises(ValueError, match="не завершён"):
            svc._validate_tests_for_comparison(tests)

    def test_comparability_uses_resolved_bundle_snapshot(self):
        svc = ComparisonService(repository=AsyncMock())
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        tests = [
            _make_test_data(id1, "A", database_group_id="ldb1"),
            _make_test_data(id2, "B", database_group_id="ldb1"),
        ]
        tests[0]["config"].update({
            "resolved_bundle_id": "bundle-a",
            "resolved_bundle_snapshot": {
                "queries": [{"query_type": "select", "sql_template": "SELECT * FROM rental"}],
            },
        })
        tests[1]["config"].update({
            "resolved_bundle_id": "bundle-a",
            "resolved_bundle_snapshot": {
                "queries": [{"query_type": "select", "sql_template": "SELECT * FROM payment"}],
            },
        })

        report = svc._build_comparability_report(tests)

        assert report.same_query_ids is False
        assert report.is_valid_for_series is False


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
    async def test_per_test_throughput_summary_uses_aggregate_metrics(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Brazilian E-com", db_keys=["conn_mysql"])
        run["results"][0]["metrics"]["throughput"] = 368.08402309551104
        run["results"][0]["metrics"]["tps"] = 368.08402309551104
        run["results"][0]["metrics"]["successful"] = 750
        run["results"][0]["metrics"]["total_time_ms"] = 18806.213304955236
        test_data = {str(id1): run}
        samples = {
            str(id1): _make_throughput_samples("conn_mysql", batch_values=[60.0, 5.0, 75.0]),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        throughput = result.descriptive_stats["conn_mysql"].throughput
        assert throughput is not None
        assert throughput.mean == pytest.approx(368.08402309551104)
        assert result.descriptive_stats["conn_mysql"].total_duration_sec == pytest.approx(2.0375782510000136)
        assert result.charts.bar_chart[0].throughput_mean == pytest.approx(368.08402309551104)

    @pytest.mark.asyncio
    async def test_bar_chart_exposes_latency_p50_not_latency_mean(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Skewed latency", db_keys=["conn_mysql"])
        test_data = {str(id1): run}
        samples = {
            str(id1): [
                {
                    "sample_type": "request_latency",
                    "connection_key": "conn_mysql",
                    "latency_ms": value,
                    "is_error": False,
                }
                for value in [1.0, 2.0, 3.0, 100.0]
            ],
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        point = result.charts.bar_chart[0]
        assert point.latency_mean == pytest.approx(26.5)
        assert point.latency_p50 == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_per_test_ranking_uses_aggregate_throughput_not_window_average(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Brazilian E-com", db_keys=["conn_mysql", "conn_pg"])
        run["results"][0]["metrics"]["throughput"] = 368.0
        run["results"][0]["metrics"]["tps"] = 368.0
        run["results"][1]["metrics"]["throughput"] = 703.0
        run["results"][1]["metrics"]["tps"] = 703.0
        test_data = {str(id1): run}
        samples = {
            str(id1): (
                _make_throughput_samples("conn_mysql", batch_values=[900.0, 950.0])
                + _make_throughput_samples("conn_pg", batch_values=[10.0, 20.0])
            ),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        throughput_ranking = next(r for r in result.rankings if r.metric == "throughput_mean")
        assert throughput_ranking.best_db_key == "conn_pg"

    @pytest.mark.asyncio
    async def test_pairwise_throughput_keeps_window_samples_for_statistical_tests(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Brazilian E-com", db_keys=["conn_mysql", "conn_pg"])
        run["results"][0]["metrics"]["throughput"] = 368.0
        run["results"][1]["metrics"]["throughput"] = 703.0
        test_data = {str(id1): run}
        samples = {
            str(id1): (
                _make_throughput_samples("conn_mysql", batch_values=[100.0, 110.0, 120.0])
                + _make_throughput_samples("conn_pg", batch_values=[200.0, 210.0, 220.0])
            ),
        }
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples.get(tid, []))

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        throughput_pair = next(p for p in result.pairwise if p.metric == "throughput")
        assert throughput_pair.baseline_mean == pytest.approx(110.0)
        assert throughput_pair.compared_mean == pytest.approx(210.0)

    @pytest.mark.asyncio
    async def test_per_test_latency_samples_are_not_filtered_by_global_warmup(self, mock_repo):
        id1 = uuid.uuid4()
        started_at = datetime(2026, 4, 28, 17, 0, 0, tzinfo=timezone.utc)
        run = _make_test_data(id1, "Sequential DB run", db_keys=["conn_mysql"])
        run["started_at"] = started_at.isoformat()
        run["config"]["warmup_time"] = 5
        test_data = {str(id1): run}
        samples = [
            {
                "sample_type": "request_latency",
                "connection_key": "conn_mysql",
                "timestamp": (started_at - timedelta(seconds=30)).isoformat(),
                "latency_ms": 10.0,
                "is_error": False,
            },
            {
                "sample_type": "request_latency",
                "connection_key": "conn_mysql",
                "timestamp": (started_at + timedelta(seconds=10)).isoformat(),
                "latency_ms": 30.0,
                "is_error": False,
            },
        ]
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(side_effect=lambda tid: samples)

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="per_test", test_ids=[id1])
        result = await svc.analyze(request)

        latency = result.descriptive_stats["conn_mysql"].latency_ms
        assert latency is not None
        assert latency.count == 2
        assert latency.mean == pytest.approx(20.0)

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
            str(id1): _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_pg"]),
            str(id2): _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_pg"]),
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
            str(id1): _make_test_data(id1, "MySQL", virtual_users=4, db_keys=["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", virtual_users=8, db_keys=["conn_pg"]),
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

    @pytest.mark.asyncio
    async def test_comparability_flags_different_warmup_profiles(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        t1 = _make_test_data(id1, "A", db_keys=["conn_pg"])
        t2 = _make_test_data(id2, "B", db_keys=["conn_pg"])
        t1["config"]["warmup_profile"] = "steady"
        t2["config"]["warmup_profile"] = "ramp_then_hold"
        test_data = {str(id1): t1, str(id2): t2}
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(return_value=[])

        svc = ComparisonService(repository=mock_repo)
        report = svc._build_comparability_report([t1, t2])
        assert any("профил" in r.lower() for r in report.reasons)

    def test_comparability_blocks_mixed_workload_modes(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        t1 = _make_test_data(id1, "Query run", db_keys=["conn_pg"])
        t2 = _make_test_data(id2, "Txn run", db_keys=["conn_pg"])
        t1["config"]["workload_mode"] = "query"
        t1["config"]["resolved_bundle_snapshot"] = {
            "workload_mode": "query",
            "queries": [{"sql_template": "SELECT 1", "query_type": "select"}],
        }
        t2["config"]["workload_mode"] = "transaction"
        t2["config"]["resolved_bundle_snapshot"] = {
            "workload_mode": "transaction",
            "transactions": [{
                "name": "tx1",
                "steps": [{"sql_template": "SELECT 1", "query_type": "select", "order_index": 0}],
            }],
        }

        svc = ComparisonService(repository=mock_repo)
        report = svc._build_comparability_report([t1, t2])
        assert report.same_workload_mode is False
        assert report.is_valid_for_series is False
        assert any("transaction-level" in reason for reason in report.reasons)


# ---------------------------------------------------------------------------
# Sampling / source consistency regressions
# ---------------------------------------------------------------------------

def _make_latency_only_samples(db_key: str, n: int, base_ms: float = 10.0) -> List[Dict[str, Any]]:
    return [
        {
            "sample_type": "request_latency",
            "connection_key": db_key,
            "db_type": "postgresql",
            "latency_ms": base_ms + (i % 7),
            "is_error": False,
        }
        for i in range(n)
    ]


class TestComparisonSampling:
    @pytest.mark.asyncio
    async def test_fetch_metric_samples_passes_connection_key(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Multi", db_keys=["conn_mysql", "conn_pg"])
        run["results"][0]["metrics"]["throughput"] = 100.0
        run["results"][0]["metrics"]["p95_time_ms"] = 50.0
        run["results"][0]["metrics"]["avg_time_ms"] = 30.0
        run["results"][1]["metrics"]["throughput"] = 200.0
        run["results"][1]["metrics"]["p95_time_ms"] = 40.0
        run["results"][1]["metrics"]["avg_time_ms"] = 25.0
        mock_repo.get_test_run_with_results = AsyncMock(return_value=run)
        mock_repo.get_metric_samples = AsyncMock(return_value=_make_metric_samples("conn_pg", n=50))
        mock_repo.count_metric_samples = AsyncMock(return_value=50)

        svc = ComparisonService(repository=mock_repo)
        await svc._collect_metric_samples(str(id1), "conn_pg", run)

        mock_repo.get_metric_samples.assert_awaited()
        call_kwargs = mock_repo.get_metric_samples.await_args.kwargs
        assert call_kwargs.get("connection_key") == "conn_pg"
        assert call_kwargs.get("limit") is None

    @pytest.mark.asyncio
    async def test_multi_db_global_limit_starves_other_db_without_connection_key(self, mock_repo):
        """Регрессия: без фильтра по connection_key вторая СУБД не получает raw latency."""
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Heavy", db_keys=["conn_mysql", "conn_pg"], virtual_users=50, iterations=500)
        for r in run["results"]:
            r["metrics"]["throughput"] = 500.0
            r["metrics"]["p95_time_ms"] = 60.0
            r["metrics"]["avg_time_ms"] = 40.0
            r["metrics"]["successful"] = 12000

        mysql_samples = _make_latency_only_samples("conn_mysql", 10000, base_ms=5.0)
        pg_samples = _make_latency_only_samples("conn_pg", 5000, base_ms=200.0)

        async def legacy_get_samples(test_id, **kwargs):
            if kwargs.get("connection_key"):
                if kwargs["connection_key"] == "conn_mysql":
                    return mysql_samples
                if kwargs["connection_key"] == "conn_pg":
                    return pg_samples
                return []
            return mysql_samples[:10000]

        mock_repo.get_test_run_with_results = AsyncMock(return_value=run)
        mock_repo.get_metric_samples = AsyncMock(side_effect=legacy_get_samples)
        mock_repo.count_metric_samples = AsyncMock(return_value=5000)
        mock_repo.get_time_series = AsyncMock(return_value=[])

        svc = ComparisonService(repository=mock_repo)
        pg_info = await svc._collect_metric_samples(str(id1), "conn_pg", run)
        mysql_info = await svc._collect_metric_samples(str(id1), "conn_mysql", run)

        assert len(mysql_info["latency_values"]) == 10000
        assert len(pg_info["latency_values"]) == 5000
        pg_p95 = calculate_descriptive_stats(pg_info["latency_values"]).p95
        mysql_p95 = calculate_descriptive_stats(mysql_info["latency_values"]).p95
        assert pg_p95 > 150.0
        assert mysql_p95 < 20.0

    @pytest.mark.asyncio
    async def test_standard_mixed_sources_no_warning(self, mock_repo):
        """Штатный режим: latency из metric_samples, throughput из итогов прогона."""
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Mixed", db_keys=["conn_pg"])
        run["results"][0]["metrics"]["throughput"] = 400.0
        run["results"][0]["metrics"]["tps"] = 400.0
        mock_repo.get_test_run_with_results = AsyncMock(return_value=run)
        mock_repo.get_metric_samples = AsyncMock(return_value=_make_metric_samples("conn_pg", n=30))
        mock_repo.count_metric_samples = AsyncMock(return_value=30)

        svc = ComparisonService(repository=mock_repo)
        warnings: List = []
        info = await svc._collect_metric_samples(str(id1), "conn_pg", run)
        bundle = svc._build_metric_bundle(info, warnings, run["name"], "conn_pg")

        assert bundle.source == "standard_mixed"
        assert bundle.data_quality == "standard"
        assert bundle.throughput_semantics == "run_aggregate"
        assert not any("разных источников" in getattr(w, "message", str(w)) for w in warnings)

    @pytest.mark.asyncio
    async def test_degraded_mixed_sources_emits_warning(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Degraded", db_keys=["conn_pg"])
        mock_repo.get_test_run_with_results = AsyncMock(return_value=run)
        mock_repo.get_metric_samples = AsyncMock(return_value=[])
        mock_repo.count_metric_samples = AsyncMock(return_value=0)
        mock_repo.get_time_series = AsyncMock(return_value=[
            {"response_time": 50.0, "tps": 100.0},
            {"response_time": 55.0, "tps": 110.0},
        ])

        svc = ComparisonService(repository=mock_repo)
        warnings: List = []
        info = await svc._collect_metric_samples(str(id1), "conn_pg", run)
        bundle = svc._build_metric_bundle(info, warnings, run["name"], "conn_pg")

        assert bundle.source == "mixed_sources"
        assert bundle.data_quality == "degraded"
        assert any("несогласованных источников" in getattr(w, "message", str(w)) for w in warnings)

    @pytest.mark.asyncio
    async def test_time_series_throughput_prefers_tps(self, mock_repo):
        svc = ComparisonService(repository=AsyncMock())
        points = [
            {"tps": 120.0, "throughput": 999.0, "response_time": 10.0},
            {"tps": 130.0, "throughput": 888.0, "response_time": 11.0},
        ]
        values = svc._extract_time_series_throughput(points)
        assert values == [120.0, 130.0]

    @pytest.mark.asyncio
    async def test_latency_excludes_errors(self, mock_repo):
        svc = ComparisonService(repository=AsyncMock())
        samples = [
            {"sample_type": "request_latency", "latency_ms": 10.0, "is_error": False},
            {"sample_type": "request_latency", "latency_ms": 500.0, "is_error": True},
        ]
        values = svc._extract_latency_values(samples)
        assert values == [10.0]

    @pytest.mark.asyncio
    async def test_series_duplicate_load_level_blocks_analysis(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        t1 = _make_test_data(id1, "A", virtual_users=10, iterations=100, db_keys=["conn_pg"])
        t2 = _make_test_data(id2, "B", virtual_users=10, iterations=100, db_keys=["conn_pg"])
        test_data = {str(id1): t1, str(id2): t2}
        mock_repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: test_data.get(tid))
        mock_repo.get_metric_samples = AsyncMock(
            side_effect=lambda tid, **kw: _make_metric_samples("conn_pg", n=50)
        )
        mock_repo.count_metric_samples = AsyncMock(return_value=50)

        svc = ComparisonService(repository=mock_repo)
        request = ComparisonRequest(analysis_mode="series", test_ids=[id1, id2])
        with pytest.raises(ValueError, match="несопоставимы"):
            await svc.analyze(request)

    def test_comparability_blocks_different_schema_profiles(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        t1 = _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_pg"])
        t2 = _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_pg"])
        t1["config"]["resolved_profile_id"] = "profile-a"
        t2["config"]["resolved_profile_id"] = "profile-b"

        svc = ComparisonService(repository=mock_repo)
        report = svc._build_comparability_report([t1, t2])
        assert report.same_schema_profile is False
        assert report.is_valid_for_series is False
        assert any("профил" in r.lower() for r in report.reasons)

    def test_comparability_blocks_different_warmup_for_series(self, mock_repo):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        t1 = _make_test_data(id1, "A", virtual_users=4, db_keys=["conn_pg"])
        t2 = _make_test_data(id2, "B", virtual_users=8, db_keys=["conn_pg"])
        t1["config"]["warmup_mode"] = "active"
        t2["config"]["warmup_mode"] = "skip"

        svc = ComparisonService(repository=mock_repo)
        report = svc._build_comparability_report([t1, t2])
        assert report.is_valid_for_series is False
        assert any("прогрев" in r.lower() for r in report.reasons)

    @pytest.mark.asyncio
    async def test_warmup_phase_excluded_from_latency(self, mock_repo):
        svc = ComparisonService(repository=AsyncMock())
        samples = [
            {"sample_type": "request_latency", "latency_ms": 5.0, "measurement_phase": "warmup"},
            {"sample_type": "request_latency", "latency_ms": 20.0, "measurement_phase": "measurement"},
            {"sample_type": "request_latency", "latency_ms": 30.0},
        ]
        values = svc._extract_latency_values(samples)
        assert values == [20.0, 30.0]

    @pytest.mark.asyncio
    async def test_inferential_reliability_limited_for_large_request_sample(self, mock_repo):
        id1 = uuid.uuid4()
        run = _make_test_data(id1, "Large", db_keys=["conn_pg"])
        run["results"][0]["metrics"]["throughput"] = 400.0
        mock_repo.get_test_run_with_results = AsyncMock(return_value=run)
        mock_repo.get_metric_samples = AsyncMock(
            return_value=_make_metric_samples("conn_pg", n=600)
        )
        mock_repo.count_metric_samples = AsyncMock(return_value=600)

        svc = ComparisonService(repository=mock_repo)
        info = await svc._collect_metric_samples(str(id1), "conn_pg", run)
        bundle = svc._build_metric_bundle(info, [], run["name"], "conn_pg")
        assert bundle.inferential_reliability == "limited"
