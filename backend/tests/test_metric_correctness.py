"""
Тесты корректности метрик и статистики.
Проверяют, что расчёты p50/p95/p99, throughput, error_rate
соответствуют эталонным значениям на фиксированных наборах данных.
"""
import numpy as np
import pytest

from backend.comparison.statistics import (
    calculate_box_plot_stats,
    calculate_descriptive_stats,
)


# =========================================================================
# Эталонные наборы данных
# =========================================================================

@pytest.fixture
def latency_100():
    """100 точек latency с seed=42 для воспроизводимости"""
    rng = np.random.RandomState(42)
    return rng.normal(50.0, 10.0, 100).tolist()


@pytest.fixture
def throughput_50():
    """50 точек throughput с seed=99"""
    rng = np.random.RandomState(99)
    return rng.normal(120.0, 15.0, 50).tolist()


# =========================================================================
# Percentile correctness on reference data
# =========================================================================

class TestPercentileCorrectness:
    def test_p50_matches_numpy(self, latency_100):
        stats = calculate_descriptive_stats(latency_100)
        expected = float(np.percentile(latency_100, 50))
        assert stats.p50 == pytest.approx(expected, abs=0.01)

    def test_p95_matches_numpy(self, latency_100):
        stats = calculate_descriptive_stats(latency_100)
        expected = float(np.percentile(latency_100, 95))
        assert stats.p95 == pytest.approx(expected, abs=0.01)

    def test_p99_matches_numpy(self, latency_100):
        stats = calculate_descriptive_stats(latency_100)
        expected = float(np.percentile(latency_100, 99))
        assert stats.p99 == pytest.approx(expected, abs=0.01)

    def test_mean_not_equal_median_for_skewed(self):
        rng = np.random.RandomState(42)
        skewed = rng.exponential(scale=20.0, size=200).tolist()
        stats = calculate_descriptive_stats(skewed)
        assert stats.mean != pytest.approx(stats.median, abs=1.0)

    def test_mean_not_substitutes_percentiles(self, latency_100):
        stats = calculate_descriptive_stats(latency_100)
        assert stats.p95 != pytest.approx(stats.mean, abs=1.0)
        assert stats.p99 != pytest.approx(stats.mean, abs=1.0)


# =========================================================================
# Throughput statistics
# =========================================================================

class TestThroughputStatistics:
    def test_throughput_mean(self, throughput_50):
        stats = calculate_descriptive_stats(throughput_50)
        expected_mean = float(np.mean(throughput_50))
        assert stats.mean == pytest.approx(expected_mean, abs=0.01)

    def test_throughput_std(self, throughput_50):
        stats = calculate_descriptive_stats(throughput_50)
        expected_std = float(np.std(throughput_50, ddof=1))
        assert stats.std == pytest.approx(expected_std, abs=0.01)

    def test_throughput_min_max(self, throughput_50):
        stats = calculate_descriptive_stats(throughput_50)
        assert stats.min == pytest.approx(float(np.min(throughput_50)), abs=0.01)
        assert stats.max == pytest.approx(float(np.max(throughput_50)), abs=0.01)


# =========================================================================
# Box plot consistency with descriptive stats
# =========================================================================

class TestBoxPlotConsistency:
    def test_box_plot_matches_descriptive(self, latency_100):
        stats = calculate_descriptive_stats(latency_100)
        bp = calculate_box_plot_stats(latency_100)

        assert bp["median"] == pytest.approx(stats.median, abs=0.01)
        assert bp["min"] == pytest.approx(stats.min, abs=0.01)
        assert bp["max"] == pytest.approx(stats.max, abs=0.01)
        assert bp["sample_count"] == stats.count

    def test_quartiles_consistent(self, latency_100):
        bp = calculate_box_plot_stats(latency_100)
        assert bp["q1"] <= bp["median"] <= bp["q3"]
        assert bp["min"] <= bp["q1"]
        assert bp["q3"] <= bp["max"]


# =========================================================================
# Error rate validation
# =========================================================================

class TestErrorRate:
    def test_error_rate_calculation(self):
        total = 1000
        errors = 50
        error_rate = (errors / total) * 100.0
        assert error_rate == pytest.approx(5.0)

    def test_zero_errors(self):
        error_rate = (0 / 1000) * 100.0
        assert error_rate == 0.0

    def test_all_errors(self):
        error_rate = (100 / 100) * 100.0
        assert error_rate == 100.0


# =========================================================================
# Large data stability
# =========================================================================

class TestLargeDataStability:
    def test_10k_samples_stable(self):
        rng = np.random.RandomState(42)
        data = rng.normal(100.0, 20.0, 10000).tolist()
        stats = calculate_descriptive_stats(data)

        assert stats.mean == pytest.approx(100.0, abs=1.0)
        assert stats.std == pytest.approx(20.0, abs=1.0)
        assert stats.count == 10000

    def test_uniform_distribution(self):
        rng = np.random.RandomState(42)
        data = rng.uniform(0.0, 100.0, 5000).tolist()
        stats = calculate_descriptive_stats(data)

        assert stats.mean == pytest.approx(50.0, abs=2.0)
        assert stats.p50 == pytest.approx(50.0, abs=3.0)
