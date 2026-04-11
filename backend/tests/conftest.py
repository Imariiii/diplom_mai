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
    AnalysisReportConfig,
    ComparisonResult,
    ComparisonTestInfo,
    ComparisonType,
    DescriptiveStats,
    MetricStatsBundle,
    NormalizedMetrics,
    PairwiseComparison,
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
    baseline_id: uuid.UUID,
    compared_id: uuid.UUID,
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
        baseline_test_id=baseline_id,
        compared_test_id=compared_id,
        db_key=db_key,
        metric=metric,
        baseline_mean=100.0,
        compared_mean=110.0,
        pct_difference=pct_difference,
        test_used="welch_ttest",
        statistic=3.5,
        p_value=p_value,
        is_significant=is_significant,
        interpretation="Сравниваемый тест показывает прирост на 10.0%",
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
def cross_database_result(two_test_ids):
    """Минимальный ComparisonResult типа CROSS_DATABASE"""
    baseline_id, compared_id = two_test_ids
    return ComparisonResult(
        tests=[
            make_test_info(baseline_id, "MySQL Test"),
            make_test_info(compared_id, "PostgreSQL Test"),
        ],
        baseline_id=baseline_id,
        comparison_type=ComparisonType.CROSS_DATABASE,
        descriptive_stats={
            str(baseline_id): {"db1": MetricStatsBundle(
                latency_ms=make_descriptive_stats(mean=45.0),
                throughput=make_descriptive_stats(mean=100.0),
                source="raw_samples",
            )},
            str(compared_id): {"db1": MetricStatsBundle(
                latency_ms=make_descriptive_stats(mean=50.0),
                throughput=make_descriptive_stats(mean=110.0),
                source="raw_samples",
            )},
        },
        pairwise_comparisons=[
            make_pairwise(baseline_id, compared_id, metric="throughput", pct_difference=10.0),
            make_pairwise(baseline_id, compared_id, metric="latency_ms", pct_difference=11.1),
        ],
    )


@pytest.fixture
def scalability_result():
    """ComparisonResult типа SCALABILITY (разные VU)"""
    id1, id2 = make_uuid(), make_uuid()
    return ComparisonResult(
        tests=[
            make_test_info(id1, "4 VU", virtual_users=4),
            make_test_info(id2, "8 VU", virtual_users=8),
        ],
        baseline_id=id1,
        comparison_type=ComparisonType.SCALABILITY,
        descriptive_stats={
            str(id1): {"db1": MetricStatsBundle(
                throughput=make_descriptive_stats(mean=100.0),
                latency_ms=make_descriptive_stats(mean=40.0),
                source="raw_samples",
            )},
            str(id2): {"db1": MetricStatsBundle(
                throughput=make_descriptive_stats(mean=180.0),
                latency_ms=make_descriptive_stats(mean=55.0),
                source="raw_samples",
            )},
        },
        pairwise_comparisons=[
            make_pairwise(id1, id2, metric="throughput", pct_difference=80.0),
            make_pairwise(id1, id2, metric="latency_ms", pct_difference=37.5),
        ],
        normalized_metrics={
            str(id1): {"db1": NormalizedMetrics(
                throughput_abs=100.0, latency_mean_abs=40.0,
                throughput_per_thread=25.0, scaling_efficiency=1.0,
                threads=4, duration_seconds=60.0,
                source_metrics=["throughput"],
            )},
            str(id2): {"db1": NormalizedMetrics(
                throughput_abs=180.0, latency_mean_abs=55.0,
                throughput_per_thread=22.5, scaling_efficiency=0.9,
                threads=8, duration_seconds=60.0,
                source_metrics=["throughput"],
            )},
        },
    )


@pytest.fixture
def temporal_result():
    """ComparisonResult типа TEMPORAL"""
    id1, id2 = make_uuid(), make_uuid()
    return ComparisonResult(
        tests=[
            make_test_info(id1, "Run Jan"),
            make_test_info(id2, "Run Feb"),
        ],
        baseline_id=id1,
        comparison_type=ComparisonType.TEMPORAL,
        descriptive_stats={
            str(id1): {"db1": MetricStatsBundle(
                throughput=make_descriptive_stats(mean=100.0),
                latency_ms=make_descriptive_stats(mean=50.0),
                source="raw_samples",
            )},
            str(id2): {"db1": MetricStatsBundle(
                throughput=make_descriptive_stats(mean=95.0),
                latency_ms=make_descriptive_stats(mean=55.0),
                source="raw_samples",
            )},
        },
        pairwise_comparisons=[
            make_pairwise(id1, id2, metric="throughput", pct_difference=-5.0, is_significant=False, p_value=0.12),
            make_pairwise(id1, id2, metric="latency_ms", pct_difference=10.0, is_significant=True, p_value=0.03),
        ],
    )
