"""
Unit-тесты для backend/analysis/report_generator.py
Проверка генерации вердиктов, паттернов, рекомендаций, гипотез
для каждого ComparisonType.
"""
import uuid

import pytest

from backend.analysis.report_generator import ComparisonReportGenerator
from backend.comparison.schemas import (
    AnalysisReportConfig,
    ComparisonResult,
    ComparisonTraits,
    ComparisonType,
    MetricStatsBundle,
    PairwiseComparison,
)
from backend.tests.conftest import make_descriptive_stats, make_pairwise, make_test_info, make_uuid


@pytest.fixture
def generator():
    return ComparisonReportGenerator()


# =========================================================================
# Вердикты — CROSS_DATABASE
# =========================================================================

class TestCrossDatabaseVerdict:
    def test_clear_leader(self, generator, cross_database_result):
        verdict = generator.generate_verdict(cross_database_result)
        assert "лидер" in verdict or "показывает" in verdict

    def test_parity(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "MySQL"), make_test_info(id2, "PG")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={},
            pairwise_comparisons=[
                make_pairwise(id1, id2, metric="throughput",
                              pct_difference=2.0, is_significant=False, p_value=0.35),
            ],
        )
        verdict = generator.generate_verdict(result)
        assert "идентичную" in verdict or "незначим" in verdict.lower()

    def test_no_throughput_data(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "A"), make_test_info(id2, "B")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={},
            pairwise_comparisons=[
                make_pairwise(id1, id2, metric="latency_ms", pct_difference=5.0),
            ],
        )
        verdict = generator.generate_verdict(result)
        assert "Недостаточно данных" in verdict


# =========================================================================
# Вердикты — TEMPORAL
# =========================================================================

class TestTemporalVerdict:
    _temporal_traits = ComparisonTraits(is_temporal=True)

    def test_improvement(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Jan"), make_test_info(id2, "Feb")],
            baseline_id=id1,
            comparison_type=ComparisonType.TEMPORAL,
            traits=self._temporal_traits,
            descriptive_stats={},
            pairwise_comparisons=[
                make_pairwise(id1, id2, metric="throughput",
                              pct_difference=15.0, is_significant=True, p_value=0.002),
            ],
        )
        verdict = generator.generate_verdict(result)
        assert "улучшение" in verdict

    def test_regression(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Jan"), make_test_info(id2, "Feb")],
            baseline_id=id1,
            comparison_type=ComparisonType.TEMPORAL,
            traits=self._temporal_traits,
            descriptive_stats={},
            pairwise_comparisons=[
                make_pairwise(id1, id2, metric="latency_ms",
                              pct_difference=20.0, is_significant=True, p_value=0.01),
                make_pairwise(id1, id2, metric="throughput",
                              pct_difference=-3.0, is_significant=False, p_value=0.12),
            ],
        )
        verdict = generator.generate_verdict(result)
        assert "регрессия" in verdict.lower() or "выросло" in verdict

    def test_no_data(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "A"), make_test_info(id2, "B")],
            baseline_id=id1,
            comparison_type=ComparisonType.TEMPORAL,
            traits=self._temporal_traits,
            descriptive_stats={},
            pairwise_comparisons=[],
        )
        verdict = generator.generate_verdict(result)
        assert "Недостаточно данных" in verdict

    def test_no_significant_changes(self, generator, temporal_result):
        verdict = generator.generate_verdict(temporal_result)
        assert isinstance(verdict, str) and len(verdict) > 10


# =========================================================================
# Вердикты — SCALABILITY
# =========================================================================

class TestScalabilityVerdict:
    def test_fallback_not_enough_data(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[
                make_test_info(id1, "4VU", virtual_users=4),
                make_test_info(id2, "8VU", virtual_users=8),
            ],
            baseline_id=id1,
            comparison_type=ComparisonType.SCALABILITY,
            traits=ComparisonTraits(
                same_scenario=True, same_db_targets=True, multiple_dbs=False,
                same_load_params=False, diff_virtual_users=True,
            ),
            descriptive_stats={},
            pairwise_comparisons=[],
            normalized_metrics={},
        )
        verdict = generator.generate_verdict(result)
        assert "параметр" in verdict.lower() or "нормализованные" in verdict.lower()


# =========================================================================
# Вердикты — MIXED
# =========================================================================

class TestConfigComparisonVerdict:
    def test_config_comparison_fallback(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "A", virtual_users=4), make_test_info(id2, "B", virtual_users=8)],
            baseline_id=id1,
            comparison_type=ComparisonType.CONFIG_COMPARISON,
            traits=ComparisonTraits(
                same_scenario=True, same_db_targets=True, multiple_dbs=True,
                same_load_params=False, diff_virtual_users=True,
            ),
            descriptive_stats={},
            pairwise_comparisons=[],
            normalized_metrics={},
        )
        verdict = generator.generate_verdict(result)
        assert "нормализованные" in verdict.lower() or "параметр" in verdict.lower()


# =========================================================================
# analyze_patterns
# =========================================================================

class TestAnalyzePatterns:
    def test_returns_list(self, generator, cross_database_result):
        patterns = generator.analyze_patterns(cross_database_result)
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_high_variability_detected(self, generator):
        id1 = make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Test")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={
                str(id1): {"db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=50.0, std=30.0, p99=200.0, median=45.0, p50=45.0),
                    source="raw_samples",
                )},
            },
            pairwise_comparisons=[],
        )
        patterns = generator.analyze_patterns(result)
        found = any("вариативность" in p or "хвост" in p for p in patterns)
        assert found

    def test_error_rate_detected(self, generator):
        id1 = make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Err")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={
                str(id1): {"db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(),
                    error_rate=5.0,
                    source="raw_samples",
                )},
            },
            pairwise_comparisons=[],
        )
        patterns = generator.analyze_patterns(result)
        found = any("ошибки" in p for p in patterns)
        assert found

    def test_no_patterns_fallback(self, generator):
        id1 = make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Clean")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={
                str(id1): {"db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=3.0, std=0.5, p99=8.0, median=2.8, p50=2.8, cv=0.16),
                    source="raw_samples",
                )},
            },
            pairwise_comparisons=[],
        )
        patterns = generator.analyze_patterns(result)
        assert len(patterns) >= 1


# =========================================================================
# generate_recommendations
# =========================================================================

class TestGenerateRecommendations:
    def test_returns_list(self, generator, cross_database_result):
        recs = generator.generate_recommendations(cross_database_result)
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_warnings_trigger_recommendation(self, generator):
        id1, id2 = make_uuid(), make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "A"), make_test_info(id2, "B")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            warnings=["Недостаточно данных для одной из СУБД"],
            descriptive_stats={},
            pairwise_comparisons=[],
        )
        recs = generator.generate_recommendations(result)
        found = any("предупреждений" in r.lower() or "повтори" in r.lower() for r in recs)
        assert found


# =========================================================================
# generate_hypotheses
# =========================================================================

class TestGenerateHypotheses:
    def test_returns_list(self, generator, cross_database_result):
        hyp = generator.generate_hypotheses(cross_database_result)
        assert isinstance(hyp, list)
        assert len(hyp) > 0

    def test_empty_comparisons_fallback(self, generator):
        id1 = make_uuid()
        result = ComparisonResult(
            tests=[make_test_info(id1, "Solo")],
            baseline_id=id1,
            comparison_type=ComparisonType.CROSS_DATABASE,
            descriptive_stats={},
            pairwise_comparisons=[],
        )
        hyp = generator.generate_hypotheses(result)
        assert any("дополнительной диагностики" in h for h in hyp)


# =========================================================================
# generate (full report)
# =========================================================================

class TestFullReport:
    def test_full_report_structure(self, generator, cross_database_result):
        report = generator.generate(cross_database_result)

        assert report.verdict
        assert isinstance(report.patterns, list)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.hypotheses, list)
        assert len(report.sections) > 0
        section_titles = [s.title for s in report.sections]
        assert "Основной вердикт" in section_titles

    def test_config_disables_verdict(self, generator, cross_database_result):
        config = AnalysisReportConfig(include_verdict=False)
        report = generator.generate(cross_database_result, config)
        assert "отключена" in report.verdict.lower() or "отключен" in report.verdict.lower()
        section_titles = [s.title for s in report.sections]
        assert "Основной вердикт" not in section_titles

    def test_config_disables_patterns(self, generator, cross_database_result):
        config = AnalysisReportConfig(include_patterns=False)
        report = generator.generate(cross_database_result, config)
        assert report.patterns == []

    def test_config_disables_recommendations(self, generator, cross_database_result):
        config = AnalysisReportConfig(include_recommendations=False)
        report = generator.generate(cross_database_result, config)
        assert report.recommendations == []

    def test_config_disables_hypotheses(self, generator, cross_database_result):
        config = AnalysisReportConfig(include_hypotheses=False)
        report = generator.generate(cross_database_result, config)
        assert report.hypotheses == []

    def test_temporal_report(self, generator, temporal_result):
        report = generator.generate(temporal_result)
        assert report.verdict
        assert len(report.sections) > 0

    def test_scalability_report(self, generator, scalability_result):
        report = generator.generate(scalability_result)
        assert report.verdict
        assert len(report.sections) > 0
