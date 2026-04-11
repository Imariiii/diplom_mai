"""
Unit-тесты для LoadTester.calculate_percentile
Проверка корректности расчёта перцентилей и сравнение с numpy.
"""
import numpy as np
import pytest

from backend.load_tester.tester import LoadTester


@pytest.fixture
def tester():
    """Создать LoadTester без реального подключения к БД."""
    lt = LoadTester.__new__(LoadTester)
    return lt


class TestCalculatePercentile:
    def test_empty_list(self, tester):
        assert tester.calculate_percentile([], 50) == 0.0

    def test_single_element(self, tester):
        assert tester.calculate_percentile([42.0], 50) == 42.0
        assert tester.calculate_percentile([42.0], 95) == 42.0
        assert tester.calculate_percentile([42.0], 99) == 42.0

    def test_known_median(self, tester):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        p50 = tester.calculate_percentile(data, 50)
        assert p50 == pytest.approx(30.0, abs=5.0)

    @pytest.mark.parametrize("percentile", [50, 90, 95, 99])
    def test_close_to_numpy(self, tester, percentile):
        rng = np.random.RandomState(42)
        data = rng.normal(100.0, 15.0, 500).tolist()

        custom = tester.calculate_percentile(data, percentile)
        reference = float(np.percentile(data, percentile))

        # Implementation uses simple sorted-index, allow up to 2% deviation
        max_deviation = reference * 0.02 if reference != 0 else 1.0
        assert abs(custom - reference) <= max(max_deviation, 1.0), (
            f"p{percentile}: custom={custom:.2f}, numpy={reference:.2f}"
        )

    def test_p0_returns_min(self, tester):
        data = [5.0, 10.0, 15.0, 20.0]
        assert tester.calculate_percentile(data, 0) == 5.0

    def test_p100_returns_max(self, tester):
        data = [5.0, 10.0, 15.0, 20.0]
        assert tester.calculate_percentile(data, 100) == 20.0

    def test_unsorted_input(self, tester):
        data = [50.0, 10.0, 30.0, 20.0, 40.0]
        p50 = tester.calculate_percentile(data, 50)
        assert p50 == pytest.approx(30.0, abs=5.0)
