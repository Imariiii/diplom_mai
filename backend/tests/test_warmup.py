"""
Тесты политики и фазы прогрева.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.load_tester.tester import LoadTester
from backend.load_tester.warmup import (
    WARMUP_PROFILE_RAMP_HOLD,
    WARMUP_PROFILE_STEADY,
    build_warmup_metadata,
    compute_ramp_hold_seconds,
    merge_warmup_run_stats,
)


def test_compute_ramp_hold_short_warmup():
    ramp, hold, profile = compute_ramp_hold_seconds(2)
    assert ramp == 0
    assert hold == 2
    assert profile == WARMUP_PROFILE_STEADY


def test_compute_ramp_hold_long_warmup():
    ramp, hold, profile = compute_ramp_hold_seconds(10)
    assert profile == WARMUP_PROFILE_RAMP_HOLD
    assert ramp >= 1
    assert hold >= 1
    assert ramp + hold == 10


def test_build_warmup_metadata():
    meta = build_warmup_metadata(5)
    assert meta["warmup_mode"] == "active_workload"
    assert meta["warmup_excluded_from_metrics"] is True
    assert meta["warmup_placement"] == "after_prepare_before_measurement"


def test_merge_warmup_run_stats():
    merged = merge_warmup_run_stats(
        build_warmup_metadata(5),
        {
            "db1": {
                "warmup_attempted_requests": 10,
                "warmup_failed_requests": 1,
                "warmup_successful_requests": 9,
                "warmup_completed": True,
            }
        },
    )
    assert merged["warmup_attempted_requests"] == 10
    assert merged["warmup_completed"] is True


@pytest.fixture
def tester():
    lt = LoadTester.__new__(LoadTester)
    lt.db_connection = MagicMock()
    lt.db_connection.ensure_pool_size = AsyncMock()
    lt._metrics_callback = None
    lt._cancel_requested = False
    lt._warmup_stats_per_db = {}
    return lt


@pytest.mark.asyncio
async def test_run_warmup_phase_uses_concurrency(tester):
    call_count = 0
    lock = asyncio.Lock()
    max_parallel = 0
    current_parallel = 0

    async def query_func():
        nonlocal call_count, max_parallel, current_parallel
        async with lock:
            current_parallel += 1
            max_parallel = max(max_parallel, current_parallel)
        await asyncio.sleep(0.05)
        async with lock:
            current_parallel -= 1
            call_count += 1
        return {"error": None, "execution_time_ms": 1.0}

    stats = await tester.run_warmup_phase(
        db_key="conn_pg",
        warmup_time=2,
        virtual_users=4,
        query_func=query_func,
    )
    assert stats["warmup_attempted_requests"] > 0
    assert max_parallel >= 2
    assert call_count == stats["warmup_attempted_requests"]


@pytest.mark.asyncio
async def test_run_warmup_phase_records_failures(tester):
    async def failing_query():
        return {"error": "connection refused"}

    stats = await tester.run_warmup_phase(
        db_key="conn_mysql",
        warmup_time=1,
        virtual_users=1,
        query_func=failing_query,
    )
    assert stats["warmup_failed_requests"] == stats["warmup_attempted_requests"]
    assert stats["warmup_completed"] is False
