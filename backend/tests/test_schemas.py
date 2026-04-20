"""
Unit-тесты для Pydantic-схем сравнительного анализа.
Проверка валидации, дефолтов и граничных значений.
"""
import uuid

import pytest
from pydantic import ValidationError

from backend.comparison.schemas import (
    AnalysisMode,
    AnalysisReportConfig,
    ComparisonRequest,
    DescriptiveStats,
    MetricStatsBundle,
    PairwiseComparison,
)


# =========================================================================
# AnalysisMode
# =========================================================================

class TestAnalysisMode:
    def test_values(self):
        assert AnalysisMode.PER_TEST.value == "per_test"
        assert AnalysisMode.SERIES.value == "series"


# =========================================================================
# ComparisonRequest
# =========================================================================

class TestComparisonRequest:
    def test_per_test_single_id(self):
        req = ComparisonRequest(analysis_mode="per_test", test_ids=[uuid.uuid4()])
        assert len(req.test_ids) == 1
        assert req.analysis_mode == AnalysisMode.PER_TEST

    def test_per_test_multiple_ids_raises(self):
        with pytest.raises(ValidationError):
            ComparisonRequest(analysis_mode="per_test", test_ids=[uuid.uuid4(), uuid.uuid4()])

    def test_series_two_ids(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        req = ComparisonRequest(analysis_mode="series", test_ids=ids)
        assert len(req.test_ids) == 2

    def test_series_five_ids(self):
        ids = [uuid.uuid4() for _ in range(5)]
        req = ComparisonRequest(analysis_mode="series", test_ids=ids)
        assert len(req.test_ids) == 5

    def test_series_single_id_raises(self):
        with pytest.raises(ValidationError):
            ComparisonRequest(analysis_mode="series", test_ids=[uuid.uuid4()])

    def test_series_too_many_ids_raises(self):
        with pytest.raises(ValidationError):
            ComparisonRequest(analysis_mode="series", test_ids=[uuid.uuid4() for _ in range(6)])

    def test_baseline_id_optional(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        req = ComparisonRequest(analysis_mode="series", test_ids=ids)
        assert req.baseline_id is None

    def test_baseline_id_set(self):
        ids = [uuid.uuid4(), uuid.uuid4()]
        req = ComparisonRequest(analysis_mode="series", test_ids=ids, baseline_id=ids[0])
        assert req.baseline_id == ids[0]

    def test_report_config_optional(self):
        req = ComparisonRequest(analysis_mode="per_test", test_ids=[uuid.uuid4()])
        assert req.report_config is None


# =========================================================================
# DescriptiveStats
# =========================================================================

class TestDescriptiveStats:
    def test_valid_creation(self):
        ds = DescriptiveStats(
            count=100, mean=50.0, median=48.0, std=10.0,
            min=20.0, max=90.0, p50=48.0, p95=70.0, p99=85.0,
        )
        assert ds.cv == 0.0
        assert ds.iqr == 0.0

    def test_with_cv_and_iqr(self):
        ds = DescriptiveStats(
            count=100, mean=50.0, median=48.0, std=10.0,
            min=20.0, max=90.0, p50=48.0, p95=70.0, p99=85.0,
            cv=0.2, iqr=15.0,
        )
        assert ds.cv == 0.2
        assert ds.iqr == 15.0


# =========================================================================
# MetricStatsBundle
# =========================================================================

class TestMetricStatsBundle:
    def test_defaults(self):
        bundle = MetricStatsBundle()
        assert bundle.latency_ms is None
        assert bundle.throughput is None
        assert bundle.error_rate is None
        assert bundle.source == "unknown"

    def test_with_data(self):
        ds = DescriptiveStats(
            count=10, mean=5.0, median=5.0, std=1.0,
            min=3.0, max=7.0, p50=5.0, p95=6.5, p99=6.9,
        )
        bundle = MetricStatsBundle(latency_ms=ds, source="raw_samples")
        assert bundle.latency_ms.mean == 5.0


# =========================================================================
# AnalysisReportConfig
# =========================================================================

class TestAnalysisReportConfig:
    def test_defaults_all_true(self):
        config = AnalysisReportConfig()
        assert config.include_verdict is True
        assert config.include_patterns is True
        assert config.include_recommendations is True
        assert config.include_hypotheses is True

    def test_disable_all(self):
        config = AnalysisReportConfig(
            include_verdict=False,
            include_patterns=False,
            include_recommendations=False,
            include_hypotheses=False,
        )
        assert config.include_verdict is False


# =========================================================================
# PairwiseComparison
# =========================================================================

class TestPairwiseComparison:
    def test_minimal(self):
        pc = PairwiseComparison(
            baseline_id="db_mysql",
            compared_id="db_pg",
            db_key="db1",
            metric="throughput",
            interpretation="Test",
        )
        assert pc.is_significant is False
        assert pc.warning is None
        assert pc.p_value is None

    def test_with_all_fields(self):
        pc = PairwiseComparison(
            baseline_id="level_1",
            compared_id="level_2",
            db_key="conn_pg",
            metric="latency_ms",
            baseline_mean=45.0,
            compared_mean=55.0,
            pct_difference=22.2,
            test_used="welch_ttest",
            statistic=3.5,
            p_value=0.001,
            is_significant=True,
            interpretation="Latency выросла значительно",
            effect_size=0.9,
            effect_size_label="large",
            ci_lower=5.0,
            ci_upper=15.0,
            p_value_adjusted=0.003,
            is_significant_adjusted=True,
        )
        assert pc.is_significant_adjusted is True
        assert pc.effect_size_label == "large"
