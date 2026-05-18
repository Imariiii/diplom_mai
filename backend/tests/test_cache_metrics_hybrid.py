"""
Тесты hybrid cache hit ratio (raw + display verdict).
"""
import pytest

from backend.database.dialects.cache_metrics import (
    CACHE_STATUS_NO_ACTIVITY,
    CACHE_STATUS_OK,
    MEANINGFULNESS_ENGINE_ONLY,
    MEANINGFULNESS_NOT_MEANINGFUL,
    build_hybrid_cache_metrics,
    compute_postgresql_statio_delta,
    evaluate_display_metric,
)
from backend.load_tester.sql_workload_classifier import ACTIVITY_SCALAR_ONLY


def test_postgresql_statio_delta_ok():
    result = compute_postgresql_statio_delta(
        {"statio_blks_hit": 100, "statio_blks_read": 10},
        {"statio_blks_hit": 200, "statio_blks_read": 20},
    )
    assert result["status"] == CACHE_STATUS_OK
    assert result["ratio"] == pytest.approx(90.9091, rel=1e-3)


def test_evaluate_display_scalar_only_hides_engine_ratio():
    raw = {
        "ratio": 99.5,
        "status": CACHE_STATUS_OK,
        "note": "engine",
        "denominator": 5000,
        "counter_source": "innodb_buffer_pool",
    }
    workload = {"ratio": None, "status": CACHE_STATUS_NO_ACTIVITY, "denominator": 0}
    display = evaluate_display_metric(
        raw, workload, {"activity_class": ACTIVITY_SCALAR_ONLY}
    )
    assert display["display_value"] is None
    assert display["meaningfulness"] == MEANINGFULNESS_NOT_MEANINGFUL


def test_hybrid_select1_innodb_no_activity():
    hybrid = build_hybrid_cache_metrics(
        {
            "innodb_buffer_pool_reads": 100,
            "innodb_buffer_pool_read_requests": 5000,
        },
        {
            "innodb_buffer_pool_reads": 100,
            "innodb_buffer_pool_read_requests": 5000,
        },
        workload_context={"activity_class": ACTIVITY_SCALAR_ONLY},
    )
    assert hybrid["cache_hit_ratio"] is None
    assert hybrid["cache_hit_ratio_status"] == CACHE_STATUS_NO_ACTIVITY


def test_hybrid_pg_engine_only_when_statio_zero():
    hybrid = build_hybrid_cache_metrics(
        {
            "blks_hit": 1000,
            "blks_read": 10,
            "statio_blks_hit": 50,
            "statio_blks_read": 0,
        },
        {
            "blks_hit": 2000,
            "blks_read": 20,
            "statio_blks_hit": 50,
            "statio_blks_read": 0,
        },
        workload_context={"activity_class": "user_table_read"},
    )
    assert hybrid["cache_hit_ratio"] is None
    assert hybrid["cache_hit_ratio_meaningfulness"] == MEANINGFULNESS_ENGINE_ONLY
