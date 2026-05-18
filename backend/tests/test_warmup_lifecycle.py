"""
Тесты порядка фаз: prepare -> warmup -> measurement для custom SQL.
"""
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from backend.load_tester.tester import LoadTester


@pytest.fixture
def tester():
    lt = LoadTester.__new__(LoadTester)
    lt.db_connection = MagicMock()
    lt.db_connection.get_dbms_type.return_value = "postgresql"
    lt.db_connection.get_connection_name.return_value = "PostgreSQL"
    lt.db_connection.ensure_pool_size = AsyncMock()
    lt.state_manager = MagicMock()
    lt.index_manager = MagicMock()
    lt.auto_restore = False
    lt._metrics_callback = MagicMock()
    lt._metrics_callback.on_test_start = AsyncMock()
    lt._metrics_callback.set_progress = MagicMock()
    lt._cancel_requested = False
    lt._measurement_start_counters = {}
    lt._measurement_end_counters = {}
    lt._workload_context = {}
    lt._warmup_stats_per_db = {}
    lt._is_streaming = False

    lt.prepare_database_for_test = AsyncMock(
        return_value={"needs_restore": False, "affected_tables": []}
    )
    lt.run_warmup_phase = AsyncMock(
        return_value={
            "warmup_attempted_requests": 5,
            "warmup_failed_requests": 0,
            "warmup_successful_requests": 5,
            "warmup_completed": True,
        }
    )
    lt.snapshot_measurement_start = AsyncMock()
    lt.snapshot_measurement_end = AsyncMock()
    lt.restore_database_after_test = AsyncMock()
    lt._build_self_check = MagicMock(return_value={})
    lt.build_metric_samples = MagicMock(return_value=[])

    async def fake_workers(db_key, iterations, virtual_users, query_func, **kwargs):
        return [{"error": None, "execution_time_ms": 10.0} for _ in range(iterations)]

    lt._run_workers = AsyncMock(side_effect=fake_workers)
    lt.execute_query = AsyncMock(
        return_value={"error": None, "execution_time_ms": 1.0}
    )
    lt.set_workload_context = MagicMock()
    lt.reset_warmup_stats = MagicMock()
    return lt


@pytest.mark.asyncio
async def test_custom_sql_warmup_after_prepare_before_measurement(tester):
    call_order = []

    async def track_prepare(*args, **kwargs):
        call_order.append("prepare")
        return {"needs_restore": False, "affected_tables": []}

    async def track_warmup(*args, **kwargs):
        call_order.append("warmup")
        return {
            "warmup_attempted_requests": 1,
            "warmup_failed_requests": 0,
            "warmup_successful_requests": 1,
            "warmup_completed": True,
        }

    async def track_snapshot_start(db_key):
        call_order.append("snapshot_start")

    async def track_workers(*args, **kwargs):
        call_order.append("workers")
        return [{"error": None, "execution_time_ms": 5.0}]

    tester.prepare_database_for_test = AsyncMock(side_effect=track_prepare)
    tester.run_warmup_phase = AsyncMock(side_effect=track_warmup)
    tester.snapshot_measurement_start = AsyncMock(side_effect=track_snapshot_start)
    tester._run_workers = AsyncMock(side_effect=track_workers)

    await tester.run_custom_sql_test(
        custom_sql="SELECT 1",
        db_types=["conn_pg"],
        iterations=2,
        virtual_users=2,
        warmup_time=3,
    )

    assert call_order.index("prepare") < call_order.index("warmup")
    assert call_order.index("warmup") < call_order.index("snapshot_start")
    assert call_order.index("snapshot_start") < call_order.index("workers")
    tester.run_warmup_phase.assert_awaited_once()
    kwargs = tester.run_warmup_phase.await_args.kwargs
    assert kwargs["virtual_users"] == 2
    assert kwargs["warmup_time"] == 3
