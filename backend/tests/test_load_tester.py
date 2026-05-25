"""
Unit-тесты для ядра backend/load_tester/tester.py.
Проверяют сбор sample-метрик, перцентили, выполнение запросов,
воркеры и streaming callback без реальных БД.
"""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from backend.load_tester.system_metrics import SystemMetricsSampler
from backend.load_tester.tester import LoadTester
from backend.websocket_manager import TestStreamingCallback as StreamingCallback


class _AsyncConnectionManager:
    """Простой async context manager для mock engine.connect()."""

    def __init__(self, connection):
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _AsyncEngine:
    """Обёртка над mock connection для async with engine.connect()."""

    def __init__(self, connection):
        self._connection = connection

    def connect(self):
        return _AsyncConnectionManager(self._connection)


@pytest.fixture
def tester():
    """Создать LoadTester без полной инициализации инфраструктуры."""
    lt = LoadTester.__new__(LoadTester)
    lt.db_connection = MagicMock()
    lt.db_connection.get_dbms_type.return_value = "postgresql"
    lt.db_connection.get_connection_name.return_value = "PostgreSQL"
    lt.db_connection.ensure_pool_size = AsyncMock()
    lt._metrics_callback = None
    lt._status_callback = None
    lt._backup_callback = None
    lt._is_streaming = False
    lt._streaming_interval = 1.0
    lt.auto_restore = True
    lt._random_value_cache = {}
    lt._random_value_cache_locks = {}
    lt._system_metrics_sampler = SystemMetricsSampler()
    lt._last_emit_interval_sec = 1.0
    lt._sample_system_metrics = MagicMock(return_value={
        "cpu_usage": 10.0,
        "memory_usage_percent": 20.0,
        "memory_usage_mb": 512.0,
        "disk_iops": 5.0,
        "network_in_mbps": 1.5,
        "network_out_mbps": 2.5,
        "disk_ops_per_sec": 12.0,
        "disk_read_mib_per_sec": 1.0,
        "disk_write_mib_per_sec": 0.5,
        "network_in_mib_per_sec": 0.2,
        "network_out_mib_per_sec": 0.3,
    })
    lt.get_system_metrics = AsyncMock(return_value=lt._sample_system_metrics.return_value)
    lt.get_dbms_metrics = AsyncMock(return_value={
        "cache_hit_ratio": 95.0,
        "buffer_pool_hit_ratio": 90.0,
        "buffer_size_mb": 512.0,
        "buffer_size_label": "shared_buffers",
        "lock_waits": 2,
        "deadlocks": 0,
    })
    lt._dbms_metrics_cache = {}
    lt._dbms_metrics_cache_at = {}
    lt._dbms_metrics_cache_ttl = 5.0
    lt._measurement_start_counters = {}
    lt._measurement_end_counters = {}
    lt._workload_context = {}
    lt._warmup_stats_per_db = {}
    lt.get_dbms_metric_counters = AsyncMock(return_value={})
    lt.run_warmup_phase = AsyncMock(
        return_value={
            "warmup_attempted_requests": 0,
            "warmup_failed_requests": 0,
            "warmup_successful_requests": 0,
            "warmup_completed": True,
        }
    )
    lt._cancel_requested = False
    return lt


class TestScenarioSqlBinding:
    def test_build_executable_sql_replaces_quoted_and_unquoted_placeholders(self, tester):
        statement = tester._build_executable_sql(
            "UPDATE payment SET last_update = '{payment_last_update}' WHERE payment_id = {payment_payment_id}",
            {
                "payment_last_update": "2020-01-01",
                "payment_payment_id": 1,
            },
        )

        assert str(statement) == (
            "UPDATE payment SET last_update = :payment_last_update "
            "WHERE payment_id = :payment_payment_id"
        )

    def test_build_executable_sql_reports_missing_placeholder(self, tester):
        with pytest.raises(KeyError):
            tester._build_executable_sql(
                "SELECT * FROM payment WHERE payment_id = {payment_payment_id}",
                {},
            )


class TestBuildMetricSamples:
    def test_build_metric_samples_creates_latency_and_throughput_records(self, tester):
        base_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        results = [
            {"query_id": "q1", "execution_time_ms": 10.0, "error": None, "timestamp": base_ts.isoformat()},
            {"query_id": "q1", "execution_time_ms": 20.0, "error": None, "timestamp": (base_ts + timedelta(milliseconds=500)).isoformat()},
            {"query_id": "q1", "execution_time_ms": 30.0, "error": None, "timestamp": (base_ts + timedelta(seconds=1)).isoformat()},
            {"query_id": "q1", "execution_time_ms": 40.0, "error": None, "timestamp": (base_ts + timedelta(seconds=3)).isoformat()},
            {"query_id": "q1", "execution_time_ms": 50.0, "error": "boom", "timestamp": (base_ts + timedelta(seconds=3, milliseconds=100)).isoformat()},
        ]

        samples = tester.build_metric_samples(results, "conn_pg", query_id="q1")

        latency_samples = [sample for sample in samples if sample["sample_type"] == "request_latency"]
        throughput_samples = [sample for sample in samples if sample["sample_type"] == "throughput_window"]

        assert len(latency_samples) == 5
        assert [sample["latency_ms"] for sample in latency_samples] == [10.0, 20.0, 30.0, 40.0, 50.0]
        assert [sample["is_error"] for sample in latency_samples] == [False, False, False, False, True]

        assert len(throughput_samples) == 3
        assert [sample["throughput"] for sample in throughput_samples] == [2.0, 1.0, 1.0]
        assert [sample["attempt_rate"] for sample in throughput_samples] == [2.0, 1.0, 2.0]
        assert [sample["latency_ms"] for sample in throughput_samples] == [15.0, 30.0, 40.0]
        assert [sample["timestamp"] for sample in throughput_samples] == [
            base_ts,
            base_ts + timedelta(seconds=1),
            base_ts + timedelta(seconds=3),
        ]

    def test_build_metric_samples_empty_input(self, tester):
        assert tester.build_metric_samples([], "conn_pg") == []

    def test_build_metric_samples_measurement_phase(self, tester):
        results = [
            {"query_id": "q1", "execution_time_ms": 10.0, "error": None},
        ]
        warmup = tester.build_metric_samples(results, "conn_pg", measurement_phase="warmup")
        measure = tester.build_metric_samples(results, "conn_pg", measurement_phase="measurement")
        assert all(s["measurement_phase"] == "warmup" for s in warmup)
        assert all(s["measurement_phase"] == "measurement" for s in measure)

    def test_build_throughput_windows_empty_input(self):
        assert LoadTester._build_throughput_windows([], [], "postgresql", "conn_pg", None) == []


class TestCalculatePercentileExtended:
    @pytest.mark.parametrize("size", [10, 100, 1000, 10000])
    @pytest.mark.parametrize("percentile", [50, 95, 99])
    def test_percentile_close_to_numpy_for_various_sizes(self, tester, size, percentile):
        rng = np.random.RandomState(size + percentile)
        data = rng.normal(100.0, 15.0, size).tolist()

        custom = tester.calculate_percentile(data, percentile)
        reference = float(np.percentile(data, percentile))
        max_deviation = max(abs(reference) * 0.02, 1.0)
        if size <= 10:
            max_deviation = max(max_deviation, 5.0)

        assert abs(custom - reference) <= max_deviation

    def test_percentile_single_value(self, tester):
        for percentile in (0, 50, 95, 99, 100):
            assert tester.calculate_percentile([42.0], percentile) == 42.0

    def test_percentile_empty(self, tester):
        assert tester.calculate_percentile([], 95) == 0.0

    def test_percentile_matches_numpy_linear_interpolation_for_skewed_small_sample(self, tester):
        data = [1.0, 2.0, 3.0, 100.0]

        assert tester.calculate_percentile(data, 50) == pytest.approx(float(np.percentile(data, 50)))
        assert tester.calculate_percentile(data, 95) == pytest.approx(float(np.percentile(data, 95)))


class TestRunCustomSqlTest:
    @pytest.mark.asyncio
    async def test_uses_wall_clock_load_elapsed_for_tps(self, tester, monkeypatch):
        tester._emit_status = AsyncMock()
        tester.prepare_database_for_test = AsyncMock(return_value={
            "needs_restore": False,
            "affected_tables": [],
        })
        tester.restore_database_after_test = AsyncMock(return_value={
            "restored": False,
            "duration_ms": 0.0,
            "verified": True,
            "errors": [],
        })
        tester._run_workers = AsyncMock(return_value=[
            {
                "query_id": "custom_sql",
                "execution_time_ms": 100.0,
                "error": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for _ in range(4)
        ])
        monkeypatch.setattr(
            "backend.load_tester.tester.time.perf_counter",
            MagicMock(side_effect=[100.0, 102.0]),
        )

        results = await tester.run_custom_sql_test(
            custom_sql="SELECT 1",
            db_types=["conn_pg"],
            iterations=4,
            virtual_users=1,
            warmup_time=0,
        )

        stats = results[0]["comparison"]["conn_pg"]
        assert stats["throughput"] == pytest.approx(2.0)
        assert stats["attempt_rate"] == pytest.approx(2.0)
        assert "tps" not in stats


class TestExecuteQuery:
    @pytest.mark.asyncio
    async def test_execute_query_success(self, tester):
        result_proxy = MagicMock()
        result_proxy.returns_rows = True
        result_proxy.fetchall.return_value = [(1,), (2,), (3,)]

        connection = MagicMock()
        connection.execute = AsyncMock(return_value=result_proxy)
        connection.commit = AsyncMock()
        engine = _AsyncEngine(connection)

        tester.db_connection.get_engine_async = AsyncMock(return_value=engine)

        result = await tester.execute_query("conn_pg", "SELECT 1", "q1")

        assert result["error"] is None
        assert result["rows_count"] == 3
        assert result["execution_time_ms"] >= 0
        connection.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_query_records_error_and_time(self, tester):
        connection = MagicMock()
        connection.execute = AsyncMock(side_effect=RuntimeError("db boom"))
        connection.commit = AsyncMock()
        engine = _AsyncEngine(connection)

        tester.db_connection.get_engine_async = AsyncMock(return_value=engine)

        result = await tester.execute_query("conn_pg", "SELECT 1", "q1")

        assert result["rows_count"] == 0
        assert "db boom" in result["error"]
        assert result["execution_time_ms"] >= 0
        connection.commit.assert_not_called()


class TestRunWorkers:
    @pytest.mark.asyncio
    async def test_run_workers_sequential_path(self, tester):
        async def query_func():
            await asyncio.sleep(0.005)
            return {
                "execution_time_ms": 5.0,
                "error": None,
            }

        start_time = time.perf_counter()
        results = await tester._run_workers("conn_pg", iterations=4, virtual_users=1, query_func=query_func)
        elapsed = time.perf_counter() - start_time

        assert len(results) == 4
        assert all(result["error"] is None for result in results)
        assert elapsed >= 0.04
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_run_workers_parallel_path_is_faster_and_emits_metrics(self, tester):
        async def query_func():
            await asyncio.sleep(0.004)
            return {
                "execution_time_ms": 4.0,
                "error": None,
            }

        sequential_start = time.perf_counter()
        sequential_results = await tester._run_workers("conn_pg", iterations=12, virtual_users=1, query_func=query_func)
        sequential_elapsed = time.perf_counter() - sequential_start

        tester._is_streaming = True
        tester._streaming_interval = 0.002
        tester._emit_metrics = AsyncMock()

        parallel_start = time.perf_counter()
        parallel_results = await tester._run_workers("conn_pg", iterations=4, virtual_users=3, query_func=query_func)
        parallel_elapsed = time.perf_counter() - parallel_start

        assert len(sequential_results) == 12
        assert len(parallel_results) == 12
        assert parallel_elapsed < sequential_elapsed
        tester.db_connection.ensure_pool_size.assert_awaited_once_with("conn_pg", 3)
        assert tester._emit_metrics.await_count >= 1

    @pytest.mark.asyncio
    async def test_run_workers_vu1_emits_final_partial_window(self, tester):
        async def query_func():
            await asyncio.sleep(0)
            return {"execution_time_ms": 5.0, "error": None}

        tester._is_streaming = True
        tester._streaming_interval = 10.0
        tester._emit_metrics = AsyncMock()

        await tester._run_workers("conn_pg", iterations=3, virtual_users=1, query_func=query_func)

        tester._emit_metrics.assert_awaited_once()
        assert tester._emit_metrics.await_args.kwargs.get("window_end_perf") is not None


class TestEmitMetrics:
    @pytest.mark.asyncio
    async def test_emit_metrics_calls_callback_with_enriched_metrics(self, tester):
        tester._metrics_callback = MagicMock()
        tester._metrics_callback.on_metrics = AsyncMock()
        tester._metrics_callback.perf_to_sample_time = MagicMock(
            return_value=(datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc), 5)
        )
        tester._is_streaming = True
        tester._measurement_start_counters["conn_pg"] = {
            "blks_hit": 1000,
            "blks_read": 100,
        }
        tester._dbms_metrics_cache["conn_pg"] = {
            "buffer_size_mb": 512.0,
            "buffer_size_label": "shared_buffers",
        }
        tester._dbms_metrics_cache_at["conn_pg"] = time.perf_counter()
        tester.get_dbms_metric_counters = AsyncMock(
            return_value={"blks_hit": 1095, "blks_read": 105}
        )

        await tester._emit_metrics(
            db_key="conn_pg",
            response_time=12.5,
            attempt_rate=34.0,
            successful=10,
            failed=1,
            window_end_perf=5.0,
        )

        tester._metrics_callback.on_metrics.assert_awaited_once()
        kwargs = tester._metrics_callback.on_metrics.await_args.kwargs
        assert kwargs["db_key"] == "conn_pg"
        assert kwargs["db_type"] == "postgresql"
        assert kwargs["db_name"] == "PostgreSQL"
        assert kwargs["response_time"] == 12.5
        assert kwargs["attempt_rate"] == 34.0
        assert kwargs["cpu_usage"] == 10.0
        assert kwargs["cache_hit_ratio"] is not None
        assert kwargs["cache_hit_ratio_status"] == "ok"
        assert kwargs["buffer_size_mb"] == 512.0
        assert kwargs["buffer_size_label"] == "shared_buffers"
        assert kwargs["sample_timestamp"] == datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)
        assert kwargs["elapsed_seconds"] == 5

    @pytest.mark.asyncio
    async def test_get_cached_dbms_metrics_reuses_cache_within_ttl(self, tester):
        tester.get_dbms_metrics = AsyncMock(return_value={"cache_hit_ratio": 80.0})
        first = await tester._get_cached_dbms_metrics("conn_pg")
        second = await tester._get_cached_dbms_metrics("conn_pg")
        assert first == second
        tester.get_dbms_metrics.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_emit_metrics_swallows_callback_errors(self, tester):
        tester._metrics_callback = MagicMock()
        tester._metrics_callback.on_metrics = AsyncMock(side_effect=RuntimeError("ws fail"))
        tester._metrics_callback.perf_to_sample_time = MagicMock(
            return_value=(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc), 0)
        )
        tester._is_streaming = True

        await tester._emit_metrics(
            db_key="conn_pg",
            response_time=10.0,
            attempt_rate=20.0,
            successful=5,
            failed=0,
        )

        tester._metrics_callback.on_metrics.assert_awaited_once()


class TestSelfCheckIntegration:
    def test_littles_law_uses_completed_requests_when_errors_exist(self, tester):
        stats = {
            "virtual_users": 30,
            "successful": 3625,
            "failed": 905,
            "avg_time_ms": 51.53,
            "throughput": 383.8,
            "avg_time_all_ms": 52.36,
            "attempt_rate": 480.6,
            "iterations": 151,
            "error_rate": 19.98,
        }

        self_check = tester._build_self_check(stats)

        assert self_check["littles_law"]["valid"] is True
        assert not any("Закон Литтла нарушен" in warning for warning in self_check["warnings"])

    @pytest.mark.asyncio
    async def test_run_scenario_test_attaches_self_check(self, tester):
        tester._emit_backup_status = AsyncMock()
        tester._emit_status = AsyncMock()
        tester._prime_random_value_cache = AsyncMock()
        tester.prepare_database_for_test = AsyncMock(return_value={
            "needs_restore": False,
            "affected_tables": [],
        })
        tester.restore_database_after_test = AsyncMock(return_value={
            "restored": False,
            "duration_ms": 0.0,
            "verified": True,
            "errors": [],
        })
        tester._run_workers = AsyncMock(return_value=[
            {"execution_time_ms": 12.0, "error": None, "timestamp": datetime.now(timezone.utc).isoformat()},
            {"execution_time_ms": 15.0, "error": None, "timestamp": datetime.now(timezone.utc).isoformat()},
        ])
        tester.build_metric_samples = MagicMock(return_value=[{"sample_type": "request_latency"}])

        stats = await tester.run_scenario_test(
            db_key="conn_pg",
            scenario={
                "name": "read_scenario",
                "scenario_type": "read_only",
                "queries": [{"sql_template": "SELECT 1", "weight": 1, "params": []}],
            },
            iterations=2,
            virtual_users=1,
            use_indexes=False,
        )

        assert "self_check" in stats
        assert "littles_law" in stats["self_check"]
        assert isinstance(stats["self_check"]["warnings"], list)


class TestStreamingCallbackSampleTime:
    def test_perf_to_sample_time_uses_wall_start(self):
        manager = MagicMock()
        callback = StreamingCallback("test-1", manager, repository=None)
        wall_start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        callback.set_wall_start(wall_start)
        callback.start_time = 100.0

        sample_ts, elapsed = callback.perf_to_sample_time(103.0)

        assert elapsed == 3
        assert sample_ts == wall_start + timedelta(seconds=3)

    @pytest.mark.asyncio
    async def test_on_metrics_uses_explicit_sample_timestamp(self):
        manager = MagicMock()
        manager.send_metrics_update = AsyncMock()
        repository = AsyncMock()
        repository.add_time_series_point = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=repository)
        explicit_ts = datetime(2026, 1, 1, 12, 0, 7, tzinfo=timezone.utc)

        await callback.on_metrics(
            db_key="conn_pg",
            db_type="postgresql",
            db_name="PostgreSQL",
            response_time=15.0,
            attempt_rate=50.0,
            throughput=4.0,
            successful=5,
            failed=1,
            sample_timestamp=explicit_ts,
            elapsed_seconds=7,
        )

        repository.add_time_series_point.assert_awaited_once()
        assert repository.add_time_series_point.await_args.kwargs["timestamp"] == explicit_ts

    @pytest.mark.asyncio
    async def test_drain_realtime_metrics_flushes_buffer(self):
        manager = MagicMock()
        manager.send_metrics_update = AsyncMock()
        repository = AsyncMock()
        repository.add_metric_sample_batch = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=repository)
        callback.metric_samples_buffer = [{"sample_type": "throughput_realtime"}]

        await callback.drain_realtime_metrics()

        repository.add_metric_sample_batch.assert_awaited_once()
        assert callback.metric_samples_buffer == []

    @pytest.mark.asyncio
    async def test_on_test_start_status_includes_elapsed_seconds(self):
        manager = MagicMock()
        manager.send_status_update = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=None)

        await callback.on_test_start()

        manager.send_status_update.assert_awaited()
        update = manager.send_status_update.await_args.args[0]
        assert update.status == "running"
        assert update.elapsed_seconds == 0

    @pytest.mark.asyncio
    async def test_on_status_change_elapsed_increases_after_start(self):
        manager = MagicMock()
        manager.send_status_update = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=None)
        await callback.on_test_start()
        callback.start_time = time.perf_counter() - 5.0

        await callback.on_status_change("running", "Прогрев…")

        update = manager.send_status_update.await_args.args[0]
        assert update.elapsed_seconds >= 5

    @pytest.mark.asyncio
    async def test_on_backup_status_includes_elapsed_seconds(self):
        manager = MagicMock()
        manager.send_status_update = AsyncMock()
        manager.send_operation_status = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=None)
        await callback.on_test_start()
        callback.start_time = time.perf_counter() - 3.0

        await callback.on_backup_status("backup_started", {"tables": ["t1"]})

        manager.send_operation_status.assert_awaited_once()
        assert manager.send_operation_status.await_args.kwargs["elapsed_seconds"] >= 3


class TestRealtimeThroughputSamples:
    @pytest.mark.asyncio
    async def test_streaming_callback_buffers_throughput_realtime_samples(self):
        manager = MagicMock()
        manager.send_metrics_update = AsyncMock()
        manager.send_operation_status = AsyncMock()
        repository = AsyncMock()
        repository.add_time_series_point = AsyncMock()
        repository.add_metric_sample_batch = AsyncMock()
        callback = StreamingCallback("test-1", manager, repository=repository)

        await callback.on_metrics(
            db_key="conn_pg",
            db_type="postgresql",
            db_name="PostgreSQL",
            response_time=15.0,
            attempt_rate=50.0,
            throughput=4.0,
            successful=5,
            failed=1,
        )

        assert len(callback.metric_samples_buffer) == 1
        assert callback.metric_samples_buffer[0]["sample_type"] == "throughput_realtime"
        assert callback.metric_samples_buffer[0]["attempt_rate"] == 50.0
        assert callback.metric_samples_buffer[0]["throughput"] == 4.0


class TestExecuteScenarioTransaction:
    @pytest.mark.asyncio
    async def test_execute_scenario_transaction_commits_all_steps(self, tester):
        conn = MagicMock()
        trans = MagicMock()
        trans.commit = AsyncMock()
        trans.rollback = AsyncMock()
        conn.begin = AsyncMock(return_value=trans)

        result_mock = MagicMock()
        result_mock.returns_rows = False
        conn.execute = AsyncMock(return_value=result_mock)

        engine = _AsyncEngine(conn)
        tester.db_connection.get_engine_async = AsyncMock(return_value=engine)

        transaction = {
            "name": "checkout",
            "steps": [
                {"sql_template": "SELECT 1", "query_type": "select"},
                {"sql_template": "UPDATE t SET x=1", "query_type": "update"},
            ],
            "params": [],
        }
        result = await tester.execute_scenario_transaction("db1", transaction, "scenario")
        assert result["error"] is None
        assert result["steps_executed"] == 2
        assert result["rollbacks"] == 0
        trans.commit.assert_awaited_once()
        assert conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_scenario_transaction_rolls_back_on_error(self, tester):
        conn = MagicMock()
        trans = MagicMock()
        trans.commit = AsyncMock()
        trans.rollback = AsyncMock()
        conn.begin = AsyncMock(return_value=trans)
        conn.execute = AsyncMock(side_effect=RuntimeError("boom"))

        engine = _AsyncEngine(conn)
        tester.db_connection.get_engine_async = AsyncMock(return_value=engine)

        transaction = {
            "name": "fail",
            "steps": [{"sql_template": "SELECT 1", "query_type": "select"}],
            "params": [],
        }
        result = await tester.execute_scenario_transaction("db1", transaction, "scenario")
        assert result["error"] is not None
        assert result["rollbacks"] == 1
        trans.rollback.assert_awaited_once()
