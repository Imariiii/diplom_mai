"""
Unit-тесты для backend/comparison/statistics.py
Проверка расчётов описательной статистики, статистических тестов,
Cohen's d, доверительных интервалов и интерпретации результатов.
"""
import math
import uuid
import warnings

import numpy as np
import pytest
from scipy import stats as sp_stats

from backend.comparison.statistics import (
    SIGNIFICANCE_LEVEL,
    MIN_SAMPLE_SIZE_FOR_TEST,
    REQUEST_LEVEL_DEPENDENT_OBSERVATION_THRESHOLD,
    _sanitize_numeric_data,
    calculate_box_plot_stats,
    calculate_cohens_d,
    calculate_confidence_interval,
    calculate_descriptive_stats,
    check_normality,
    classify_effect_size,
    compare_two_samples,
    interpret_result,
    safe_pct_difference,
)


# =========================================================================
# _sanitize_numeric_data
# =========================================================================

class TestSanitizeNumericData:
    def test_clean_data_unchanged(self):
        assert _sanitize_numeric_data([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]

    def test_removes_none(self):
        assert _sanitize_numeric_data([1.0, None, 3.0]) == [1.0, 3.0]

    def test_removes_nan(self):
        assert _sanitize_numeric_data([1.0, float("nan"), 3.0]) == [1.0, 3.0]

    def test_removes_inf(self):
        result = _sanitize_numeric_data([1.0, float("inf"), float("-inf"), 3.0])
        assert result == [1.0, 3.0]

    def test_removes_non_numeric_strings(self):
        assert _sanitize_numeric_data([1.0, "abc", 3.0]) == [1.0, 3.0]

    def test_converts_string_numbers(self):
        assert _sanitize_numeric_data(["1.5", "2.5"]) == [1.5, 2.5]

    def test_empty_input(self):
        assert _sanitize_numeric_data([]) == []

    def test_all_invalid(self):
        assert _sanitize_numeric_data([None, float("nan"), "xyz"]) == []


# =========================================================================
# calculate_descriptive_stats
# =========================================================================

class TestCalculateDescriptiveStats:
    def test_known_values(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = calculate_descriptive_stats(data)

        assert stats.count == 5
        assert stats.mean == pytest.approx(30.0)
        assert stats.median == pytest.approx(30.0)
        assert stats.min == pytest.approx(10.0)
        assert stats.max == pytest.approx(50.0)
        assert stats.p50 == pytest.approx(30.0)
        assert stats.p95 == pytest.approx(np.percentile(data, 95), abs=0.01)
        assert stats.p99 == pytest.approx(np.percentile(data, 99), abs=0.01)
        assert stats.std == pytest.approx(float(np.std(data, ddof=1)), abs=0.01)

    def test_outlier_set(self):
        data = [1.0, 1.0, 1.0, 1.0, 100.0]
        stats = calculate_descriptive_stats(data)

        assert stats.mean == pytest.approx(20.8)
        assert stats.p95 != pytest.approx(stats.mean, abs=5.0)

    def test_single_element(self):
        stats = calculate_descriptive_stats([42.0])
        assert stats.count == 1
        assert stats.mean == pytest.approx(42.0)
        assert stats.std == pytest.approx(0.0)

    def test_empty_after_sanitize_raises(self):
        with pytest.raises(ValueError, match="выборка пуста"):
            calculate_descriptive_stats([None, float("nan")])

    def test_data_with_mixed_invalid(self):
        data = [10.0, None, 20.0, float("nan"), 30.0]
        stats = calculate_descriptive_stats(data)
        assert stats.count == 3
        assert stats.mean == pytest.approx(20.0)

    def test_cv_calculation(self):
        data = [100.0, 100.0, 100.0]
        stats = calculate_descriptive_stats(data)
        assert stats.cv == pytest.approx(0.0)

    def test_iqr_calculation(self):
        data = list(range(1, 101))
        stats = calculate_descriptive_stats([float(x) for x in data])
        expected_iqr = float(np.percentile(data, 75) - np.percentile(data, 25))
        assert stats.iqr == pytest.approx(expected_iqr, abs=0.1)

    def test_large_sample_percentiles(self):
        rng = np.random.RandomState(123)
        data = rng.normal(100.0, 15.0, 1000).tolist()
        stats = calculate_descriptive_stats(data)

        assert stats.p50 == pytest.approx(np.percentile(data, 50), abs=0.01)
        assert stats.p95 == pytest.approx(np.percentile(data, 95), abs=0.01)
        assert stats.p99 == pytest.approx(np.percentile(data, 99), abs=0.01)


# =========================================================================
# calculate_box_plot_stats
# =========================================================================

class TestCalculateBoxPlotStats:
    def test_known_values(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        bp = calculate_box_plot_stats(data)

        assert bp["min"] == pytest.approx(10.0)
        assert bp["max"] == pytest.approx(50.0)
        assert bp["median"] == pytest.approx(30.0)
        assert bp["sample_count"] == 5

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            calculate_box_plot_stats([None, float("nan")])


# =========================================================================
# check_normality
# =========================================================================

class TestCheckNormality:
    def test_normal_distribution(self, sample_normal_data):
        assert check_normality(sample_normal_data) is True

    def test_exponential_distribution(self, sample_exponential_data):
        assert check_normality(sample_exponential_data) is False

    def test_too_few_samples(self):
        assert check_normality([1.0, 2.0, 3.0]) is False

    def test_exactly_min_samples_normal(self):
        rng = np.random.RandomState(99)
        data = rng.normal(0, 1, MIN_SAMPLE_SIZE_FOR_TEST).tolist()
        result = check_normality(data)
        assert isinstance(result, bool)

    def test_constant_data_passes_shapiro(self):
        # Shapiro-Wilk returns p=1 for zero-variance data (formally "normal");
        # SciPy предупреждает о нулевой дисперсии — для теста это ожидаемо.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            assert check_normality([5.0] * 20) is True


# =========================================================================
# calculate_cohens_d
# =========================================================================

class TestCalculateCohensd:
    def test_identical_samples(self):
        a = [10.0, 20.0, 30.0]
        d = calculate_cohens_d(a, a)
        assert d == pytest.approx(0.0)

    def test_known_effect(self):
        rng = np.random.RandomState(42)
        a = rng.normal(10.0, 2.0, 50).tolist()
        b = rng.normal(20.0, 2.0, 50).tolist()
        d = calculate_cohens_d(a, b)
        assert d is not None
        assert d > 0

    def test_too_few_samples(self):
        assert calculate_cohens_d([1.0], [2.0]) is None

    def test_symmetric(self):
        rng = np.random.RandomState(42)
        a = rng.normal(50, 10, 100).tolist()
        b = rng.normal(60, 10, 100).tolist()
        d_ab = calculate_cohens_d(a, b)
        d_ba = calculate_cohens_d(b, a)
        assert d_ab == pytest.approx(-d_ba, abs=0.001)

    def test_zero_std(self):
        a = [5.0, 5.0, 5.0]
        b = [5.0, 5.0, 5.0]
        d = calculate_cohens_d(a, b)
        assert d == pytest.approx(0.0)


# =========================================================================
# classify_effect_size
# =========================================================================

class TestClassifyEffectSize:
    @pytest.mark.parametrize("d,expected", [
        (None, None),
        (0.0, "negligible"),
        (0.19, "negligible"),
        (0.2, "small"),
        (0.49, "small"),
        (0.5, "medium"),
        (0.79, "medium"),
        (0.8, "large"),
        (2.0, "large"),
        (-0.3, "small"),
        (-0.9, "large"),
    ])
    def test_thresholds(self, d, expected):
        assert classify_effect_size(d) == expected


# =========================================================================
# calculate_confidence_interval
# =========================================================================

class TestCalculateConfidenceInterval:
    def test_known_difference(self):
        rng = np.random.RandomState(42)
        a = rng.normal(50, 5, 200).tolist()
        b = rng.normal(55, 5, 200).tolist()
        ci_lo, ci_hi = calculate_confidence_interval(a, b)

        true_diff = 5.0
        assert ci_lo is not None and ci_hi is not None
        assert ci_lo < true_diff < ci_hi

    def test_too_few_samples(self):
        lo, hi = calculate_confidence_interval([1.0], [2.0])
        assert lo is None and hi is None

    def test_identical_samples(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        lo, hi = calculate_confidence_interval(data, data)
        assert lo is not None and hi is not None
        assert lo <= 0.0 <= hi


# =========================================================================
# safe_pct_difference
# =========================================================================

class TestSafePctDifference:
    def test_positive_change(self):
        assert safe_pct_difference(100.0, 150.0) == pytest.approx(50.0)

    def test_negative_change(self):
        assert safe_pct_difference(100.0, 80.0) == pytest.approx(-20.0)

    def test_no_change(self):
        assert safe_pct_difference(100.0, 100.0) == pytest.approx(0.0)

    def test_zero_baseline(self):
        assert safe_pct_difference(0.0, 50.0) is None


# =========================================================================
# interpret_result
# =========================================================================

class TestInterpretResult:
    def test_no_p_value(self):
        result = interpret_result(10.0, None, "throughput")
        assert "Недостаточно данных" in result

    def test_not_significant(self):
        result = interpret_result(10.0, 0.10, "throughput")
        assert "незначима" in result

    @pytest.mark.parametrize("metric,pct,keyword", [
        ("latency_ms", 15.0, "медленнее"),
        ("latency_ms", -15.0, "быстрее"),
        ("throughput", 15.0, "прирост"),
        ("throughput", -15.0, "снижение"),
    ])
    def test_significant_directions(self, metric, pct, keyword):
        result = interpret_result(pct, 0.001, metric, "medium")
        assert keyword in result

    def test_effect_note_included(self):
        result = interpret_result(20.0, 0.01, "throughput", "large")
        assert "большой" in result

    def test_negligible_effect_not_mentioned(self):
        result = interpret_result(20.0, 0.01, "throughput", "negligible")
        assert "negligible" not in result.lower()

    def test_none_pct_diff_with_significant(self):
        result = interpret_result(None, 0.01, "throughput")
        assert "Невозможно рассчитать" in result


# =========================================================================
# compare_two_samples
# =========================================================================

class TestCompareTwoSamples:
    def _make_ids(self):
        return uuid.uuid4(), uuid.uuid4()

    def test_normal_samples_use_welch(self, sample_normal_data):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(99)
        b = rng.normal(loc=55.0, scale=10.0, size=200).tolist()

        result = compare_two_samples(
            sample_normal_data, b, baseline_id, compared_id, "db1", "latency_ms"
        )
        assert result.test_used == "welch_ttest"
        assert result.p_value is not None
        assert result.statistic is not None

    def test_non_normal_samples_use_mannwhitney(self, sample_exponential_data):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(99)
        b = rng.exponential(scale=80.0, size=200).tolist()

        result = compare_two_samples(
            sample_exponential_data, b, baseline_id, compared_id, "db1", "throughput"
        )
        assert result.test_used == "mann_whitney_u"

    def test_small_samples_no_test(self):
        baseline_id, compared_id = self._make_ids()
        result = compare_two_samples(
            [1.0, 2.0, 3.0], [4.0, 5.0, 6.0],
            baseline_id, compared_id, "db1", "latency_ms"
        )
        assert result.test_used is None
        assert result.warning is not None
        assert "Недостаточно данных" in result.warning

    def test_identical_samples_not_significant(self):
        baseline_id, compared_id = self._make_ids()
        data = list(range(1, 51))
        data_f = [float(x) for x in data]
        result = compare_two_samples(
            data_f, data_f, baseline_id, compared_id, "db1", "throughput"
        )
        assert result.is_significant is False

    def test_very_different_samples_significant(self):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(42)
        a = rng.normal(10.0, 1.0, 100).tolist()
        b = rng.normal(50.0, 1.0, 100).tolist()

        result = compare_two_samples(
            a, b, baseline_id, compared_id, "db1", "throughput"
        )
        assert result.is_significant is True
        assert result.effect_size_label == "large"

    def test_empty_sample_a(self):
        baseline_id, compared_id = self._make_ids()
        result = compare_two_samples(
            [], [1.0, 2.0, 3.0], baseline_id, compared_id, "db1", "latency_ms"
        )
        assert result.warning is not None
        assert "пуста" in result.warning

    def test_empty_sample_b(self):
        baseline_id, compared_id = self._make_ids()
        result = compare_two_samples(
            [1.0, 2.0, 3.0], [], baseline_id, compared_id, "db1", "latency_ms"
        )
        assert result.warning is not None

    def test_cohens_d_and_ci_populated(self, sample_normal_data):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(99)
        b = rng.normal(loc=60.0, scale=10.0, size=200).tolist()

        result = compare_two_samples(
            sample_normal_data, b, baseline_id, compared_id, "db1", "latency_ms"
        )
        assert result.effect_size is not None
        assert result.effect_size_label is not None
        assert result.ci_lower is not None
        assert result.ci_upper is not None

    def test_pct_difference_populated(self):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(42)
        a = rng.normal(100.0, 5.0, 50).tolist()
        b = rng.normal(120.0, 5.0, 50).tolist()

        result = compare_two_samples(
            a, b, baseline_id, compared_id, "db1", "throughput"
        )
        assert result.pct_difference is not None
        assert result.pct_difference > 0

    def test_dependent_observations_warning_for_large_latency_samples(self):
        baseline_id, compared_id = self._make_ids()
        rng = np.random.RandomState(42)
        n = REQUEST_LEVEL_DEPENDENT_OBSERVATION_THRESHOLD
        a = rng.normal(40.0, 5.0, n).tolist()
        b = rng.normal(45.0, 5.0, n).tolist()

        result = compare_two_samples(
            a, b, baseline_id, compared_id, "db1", "latency_ms",
            warn_dependent_observations=True,
        )
        assert result.warning is not None
        assert "зависимы" in result.warning
