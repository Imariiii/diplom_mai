"""
Тесты для Benjamini-Hochberg FDR correction.
"""
import uuid

import pytest

from backend.comparison.schemas import PairwiseComparison
from backend.comparison.statistics import apply_fdr_correction


def _make_comparison(p_value):
    return PairwiseComparison(
        baseline_test_id=uuid.uuid4(),
        compared_test_id=uuid.uuid4(),
        db_key="conn_pg",
        metric="throughput",
        interpretation="test",
        p_value=p_value,
    )


class TestApplyFdrCorrection:
    def test_known_p_values(self):
        comparisons = [
            _make_comparison(0.04),
            _make_comparison(0.01),
            _make_comparison(0.20),
            _make_comparison(0.03),
        ]

        apply_fdr_correction(comparisons)

        assert comparisons[0].p_value_adjusted == pytest.approx(0.0533333333)
        assert comparisons[1].p_value_adjusted == pytest.approx(0.04)
        assert comparisons[2].p_value_adjusted == pytest.approx(0.2)
        assert comparisons[3].p_value_adjusted == pytest.approx(0.0533333333)

    def test_all_significant(self):
        comparisons = [
            _make_comparison(0.001),
            _make_comparison(0.002),
            _make_comparison(0.003),
        ]

        apply_fdr_correction(comparisons)

        assert all(comparison.is_significant_adjusted for comparison in comparisons)

    def test_all_not_significant(self):
        comparisons = [
            _make_comparison(0.5),
            _make_comparison(0.6),
            _make_comparison(0.7),
        ]

        apply_fdr_correction(comparisons)

        assert not any(comparison.is_significant_adjusted for comparison in comparisons)

    def test_none_p_values_are_ignored(self):
        comparisons = [
            _make_comparison(0.01),
            _make_comparison(None),
            _make_comparison(0.03),
        ]

        apply_fdr_correction(comparisons)

        assert comparisons[0].p_value_adjusted == pytest.approx(0.02)
        assert comparisons[1].p_value_adjusted is None
        assert comparisons[2].p_value_adjusted == pytest.approx(0.03)

    def test_single_comparison_keeps_same_p_value(self):
        comparison = _make_comparison(0.02)

        apply_fdr_correction([comparison])

        assert comparison.p_value_adjusted == pytest.approx(0.02)
        assert comparison.is_significant_adjusted is True

    def test_adjusted_p_values_are_monotonic_by_rank(self):
        comparisons = [
            _make_comparison(0.07),
            _make_comparison(0.01),
            _make_comparison(0.04),
            _make_comparison(0.02),
        ]

        apply_fdr_correction(comparisons)

        ranked_adjusted = [
            comparison.p_value_adjusted
            for comparison in sorted(comparisons, key=lambda item: item.p_value or 0)
        ]
        assert ranked_adjusted == sorted(ranked_adjusted)
