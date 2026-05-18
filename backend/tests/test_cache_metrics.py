"""
Unit-тесты расчёта Cache Hit Ratio по дельте счётчиков.
"""
import pytest

from backend.database.dialects.base import DEFAULT_DBMS_METRICS
from backend.database.dialects.cache_metrics import (
    CACHE_STATUS_INVALID_COUNTER,
    CACHE_STATUS_NO_ACTIVITY,
    CACHE_STATUS_OK,
    apply_cache_hit_delta_to_metrics,
    compute_innodb_cache_delta,
    compute_postgresql_cache_delta,
)
from backend.database.dialects.mariadb import MariaDBDialect


def test_postgresql_cache_delta_ok():
    result = compute_postgresql_cache_delta(
        {"blks_hit": 1000, "blks_read": 100},
        {"blks_hit": 1100, "blks_read": 120},
    )
    assert result["status"] == CACHE_STATUS_OK
    assert result["ratio"] == pytest.approx(83.3333, rel=1e-3)


def test_postgresql_cache_delta_no_activity():
    result = compute_postgresql_cache_delta(
        {"blks_hit": 10, "blks_read": 5},
        {"blks_hit": 10, "blks_read": 5},
    )
    assert result["status"] == CACHE_STATUS_NO_ACTIVITY
    assert result["ratio"] is None


def test_innodb_cache_delta_no_activity_select1_like():
    result = compute_innodb_cache_delta(
        {"innodb_buffer_pool_reads": 100, "innodb_buffer_pool_read_requests": 5000},
        {"innodb_buffer_pool_reads": 100, "innodb_buffer_pool_read_requests": 5000},
    )
    assert result["status"] == CACHE_STATUS_NO_ACTIVITY
    assert result["ratio"] is None


def test_innodb_cache_delta_invalid_reads_gt_requests():
    result = compute_innodb_cache_delta(
        {"innodb_buffer_pool_reads": 10, "innodb_buffer_pool_read_requests": 100},
        {"innodb_buffer_pool_reads": 80, "innodb_buffer_pool_read_requests": 120},
    )
    assert result["status"] == CACHE_STATUS_INVALID_COUNTER
    assert result["ratio"] is None


def test_build_final_dbms_metrics_mariadb_select1_no_activity():
    dialect = MariaDBDialect()
    metrics = dialect.build_final_dbms_metrics(
        latest_metrics=dict(DEFAULT_DBMS_METRICS),
        start_counters={
            "innodb_buffer_pool_reads": 567,
            "innodb_buffer_pool_read_requests": 261,
        },
        end_counters={
            "innodb_buffer_pool_reads": 567,
            "innodb_buffer_pool_read_requests": 261,
        },
        runtime_stats={
            "workload_context": {"activity_class": "scalar_only"},
        },
    )
    assert metrics["cache_hit_ratio"] is None
    assert metrics["cache_hit_ratio_status"] == CACHE_STATUS_NO_ACTIVITY


def test_apply_cache_hit_delta_to_metrics():
    metrics = dict(DEFAULT_DBMS_METRICS)
    apply_cache_hit_delta_to_metrics(
        metrics,
        {"innodb_buffer_pool_reads": 0, "innodb_buffer_pool_read_requests": 0},
        {"innodb_buffer_pool_reads": 10, "innodb_buffer_pool_read_requests": 1000},
    )
    assert metrics["cache_hit_ratio_status"] == CACHE_STATUS_OK
    assert metrics["cache_hit_ratio"] == 99.0
