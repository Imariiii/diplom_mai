"""
Unit-тесты для backend/analysis/report_generator.py
Проверка генерации вердиктов, паттернов, рекомендаций, гипотез
для двух режимов анализа: PerTestReportGenerator и SeriesReportGenerator.
"""
import uuid

import pytest

from backend.analysis.report_generator import PerTestReportGenerator, SeriesReportGenerator
from backend.comparison.schemas import (
    AnalysisReportConfig,
    AnalysisWarning,
    ComparisonTestInfo,
    ComparabilityReport,
    DegradationIndex,
    DbSeriesSummary,
    LoadLevel,
    MetricStatsBundle,
    PerTestCharts,
    TrajectoryPoint,
)
from backend.tests.conftest import make_descriptive_stats, make_pairwise, make_test_info, make_uuid


# =========================================================================
# PerTestReportGenerator
# =========================================================================

class TestPerTestReport:
    def _gen(self):
        return PerTestReportGenerator()

    def _make_data(self, pairwise=None, descriptive_stats=None, db_key_labels=None):
        test = make_test_info(name="Test Run")
        return {
            "test_info": test,
            "descriptive_stats": descriptive_stats or {},
            "pairwise": pairwise or [],
            "rankings": [],
            "db_key_labels": db_key_labels or {"db1": "MySQL", "db2": "PostgreSQL"},
        }

    def test_full_report_structure(self):
        gen = self._gen()
        data = self._make_data(
            pairwise=[
                make_pairwise("db1", "db2", metric="throughput", pct_difference=10.0),
                make_pairwise("db1", "db2", metric="latency_ms", pct_difference=11.1),
            ],
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=45.0),
                    throughput=make_descriptive_stats(mean=100.0),
                    source="raw_samples",
                ),
                "db2": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=50.0),
                    throughput=make_descriptive_stats(mean=110.0),
                    source="raw_samples",
                ),
            },
        )
        report = gen.generate(**data)
        assert report.verdict
        assert isinstance(report.patterns, list)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.hypotheses, list)
        assert len(report.sections) > 0

    def test_empty_pairwise(self):
        gen = self._gen()
        data = self._make_data()
        report = gen.generate(**data)
        assert report.verdict
        assert len(report.sections) > 0

    def test_config_disables_verdict(self):
        gen = self._gen()
        data = self._make_data(
            pairwise=[make_pairwise("db1", "db2", metric="throughput")],
        )
        config = AnalysisReportConfig(include_verdict=False)
        report = gen.generate(**data, config=config)
        # Вердикт пустой, секция "Основной вердикт" отсутствует
        assert report.verdict == "" or "вердикт" not in report.verdict.lower()
        section_titles = [s.title for s in report.sections]
        assert "Основной вердикт" not in section_titles

    def test_config_disables_patterns(self):
        gen = self._gen()
        data = self._make_data()
        config = AnalysisReportConfig(include_patterns=False)
        report = gen.generate(**data, config=config)
        assert report.patterns == []

    def test_config_disables_recommendations(self):
        gen = self._gen()
        data = self._make_data()
        config = AnalysisReportConfig(include_recommendations=False)
        report = gen.generate(**data, config=config)
        assert report.recommendations == []

    def test_config_disables_hypotheses(self):
        gen = self._gen()
        data = self._make_data()
        config = AnalysisReportConfig(include_hypotheses=False)
        report = gen.generate(**data, config=config)
        assert report.hypotheses == []

    def test_high_variability_detected(self):
        gen = self._gen()
        data = self._make_data(
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=50.0, std=30.0, p99=200.0, median=45.0, p50=45.0),
                    source="raw_samples",
                ),
            },
        )
        report = gen.generate(**data)
        all_text = " ".join(report.patterns + [report.verdict])
        assert "вариативность" in all_text or "хвост" in all_text or len(report.patterns) > 0


# =========================================================================
# SeriesReportGenerator
# =========================================================================

class TestSeriesReport:
    def _gen(self):
        return SeriesReportGenerator()

    def _make_data(self, per_db=None, load_levels=None, tests=None, cross_db_ranks=None,
                   parameter_impacts=None, db_key_labels=None):
        return {
            "tests": tests or [make_test_info(name="4VU"), make_test_info(name="8VU")],
            "per_db": per_db or {},
            "load_levels": load_levels or [],
            "cross_db_ranks": cross_db_ranks or [],
            "db_key_labels": db_key_labels or {"conn_pg": "PostgreSQL"},
            "parameter_impacts": parameter_impacts or [],
        }

    def test_full_report_structure(self):
        gen = self._gen()
        per_db = {
            "conn_pg": DbSeriesSummary(
                db_key="conn_pg",
                db_label="PostgreSQL",
                trajectory=[
                    TrajectoryPoint(level_id="l1", load_label="4 VU", throughput_mean=100.0, latency_mean=40.0),
                    TrajectoryPoint(level_id="l2", load_label="8 VU", throughput_mean=180.0, latency_mean=55.0),
                ],
                degradation=DegradationIndex(p95_changes=[0.1], p99_changes=[0.15], overall_p95=0.1, overall_p99=0.15),
                stability_index=0.12,
                elasticity=0.9,
                trend_tests={},
                adjacent_level_tests=[],
                descriptive_stats_by_level={},
            ),
        }
        data = self._make_data(
            per_db=per_db,
            load_levels=[
                LoadLevel(level_id="l1", virtual_users=4, iterations=100, warmup_time=0, label="4 VU", test_ids=[]),
                LoadLevel(level_id="l2", virtual_users=8, iterations=100, warmup_time=0, label="8 VU", test_ids=[]),
            ],
        )
        report = gen.generate(**data)
        assert report.verdict
        assert isinstance(report.patterns, list)
        assert len(report.sections) > 0

    def test_empty_per_db(self):
        gen = self._gen()
        data = self._make_data()
        report = gen.generate(**data)
        assert report.verdict
        assert len(report.sections) > 0

    def test_config_disables_verdict(self):
        gen = self._gen()
        data = self._make_data()
        config = AnalysisReportConfig(include_verdict=False)
        report = gen.generate(**data, config=config)
        section_titles = [s.title for s in report.sections]
        assert "Основной вердикт" not in section_titles
