"""
Общие фикстуры для тестов backend
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import numpy as np

from backend.comparison.schemas import (
    AnalysisMode,
    AnalysisReportConfig,
    AnalysisWarning,
    ComparisonRequest,
    ComparisonTestInfo,
    DescriptiveStats,
    MetricStatsBundle,
    PairwiseComparison,
    PerTestResult,
    PerTestCharts,
    SeriesResult,
)


# ---------------------------------------------------------------------------
# Helpers for building synthetic test data
# ---------------------------------------------------------------------------

def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_test_info(
    test_id: Optional[uuid.UUID] = None,
    name: str = "Test",
    virtual_users: int = 4,
    iterations: int = 100,
    scenario: str = "mixed_light",
    logical_database_id: Optional[str] = None,
    use_indexes: Optional[bool] = None,
) -> ComparisonTestInfo:
    tid = test_id or make_uuid()
    return ComparisonTestInfo(
        id=tid,
        name=name,
        status="completed",
        config={
            "virtual_users": virtual_users,
            "iterations": iterations,
            "scenario": scenario,
        },
        summary={"total_queries": iterations * virtual_users},
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        logical_database_id=logical_database_id,
        use_indexes=use_indexes,
    )


def make_descriptive_stats(
    data: Optional[List[float]] = None,
    **overrides: Any,
) -> DescriptiveStats:
    if data is not None:
        arr = np.array(data, dtype=float)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        return DescriptiveStats(
            count=len(arr),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            p50=float(np.percentile(arr, 50)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            cv=(float(np.std(arr, ddof=1)) / float(np.mean(arr))) if float(np.mean(arr)) != 0 and len(arr) > 1 else 0.0,
            iqr=q3 - q1,
            **overrides,
        )
    defaults = dict(
        count=100, mean=50.0, median=48.0, std=10.0,
        min=20.0, max=90.0, p50=48.0, p95=70.0, p99=85.0,
        cv=0.2, iqr=15.0,
    )
    defaults.update(overrides)
    return DescriptiveStats(**defaults)


def make_pairwise(
    baseline_id: str,
    compared_id: str,
    db_key: str = "db1",
    metric: str = "throughput",
    pct_difference: Optional[float] = 10.0,
    is_significant: bool = True,
    p_value: Optional[float] = 0.001,
    effect_size: Optional[float] = 0.8,
    effect_size_label: Optional[str] = "large",
    **overrides: Any,
) -> PairwiseComparison:
    defaults = dict(
        baseline_id=baseline_id,
        compared_id=compared_id,
        db_key=db_key,
        metric=metric,
        baseline_mean=100.0,
        compared_mean=110.0,
        pct_difference=pct_difference,
        test_used="welch_ttest",
        statistic=3.5,
        p_value=p_value,
        is_significant=is_significant,
        interpretation="Сравниваемый показывает прирост на 10.0%",
        effect_size=effect_size,
        effect_size_label=effect_size_label,
        ci_lower=5.0,
        ci_upper=15.0,
    )
    defaults.update(overrides)
    return PairwiseComparison(**defaults)


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_normal_data():
    """Нормально распределённая выборка (seed=42) из 200 точек"""
    rng = np.random.RandomState(42)
    return rng.normal(loc=50.0, scale=10.0, size=200).tolist()


@pytest.fixture
def sample_exponential_data():
    """Экспоненциально распределённая выборка (seed=42) из 200 точек"""
    rng = np.random.RandomState(42)
    return rng.exponential(scale=50.0, size=200).tolist()


@pytest.fixture
def two_test_ids():
    return make_uuid(), make_uuid()


@pytest.fixture
def per_test_result():
    """Минимальный PerTestResult — один прогон, несколько СУБД."""
    test_id = make_uuid()
    db1, db2 = "conn_mysql", "conn_pg"
    return PerTestResult(
        analysis_mode="per_test",
        test=make_test_info(test_id, "Mixed Test"),
        warnings=[],
        descriptive_stats={
            db1: MetricStatsBundle(
                latency_ms=make_descriptive_stats(mean=45.0),
                throughput=make_descriptive_stats(mean=100.0),
                source="raw_samples",
            ),
            db2: MetricStatsBundle(
                latency_ms=make_descriptive_stats(mean=50.0),
                throughput=make_descriptive_stats(mean=110.0),
                source="raw_samples",
            ),
        },
        pairwise=[
            make_pairwise(db1, db2, db_key=db1, metric="throughput", pct_difference=10.0),
            make_pairwise(db1, db2, db_key=db1, metric="latency_ms", pct_difference=11.1),
        ],
        rankings=[],
        charts=PerTestCharts(bar_chart=[], box_plot=[], throughput_series={}),
        db_key_labels={db1: "MySQL", db2: "PostgreSQL"},
        resource_metrics={},
    )
