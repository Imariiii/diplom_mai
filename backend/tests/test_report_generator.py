"""
Unit-тесты для backend/analysis/report_generator.py.

Проверяют компактную структуру отчёта (per-DB scorecards, фиксированные секции),
статусы Good/Warning/Critical, отсутствие UUID в выводах и anti-duplication.
"""
import re
import uuid

from backend.analysis.report_generator import PerTestReportGenerator, SeriesReportGenerator
from backend.comparison.schemas import (
    AnalysisReportConfig,
    ChangedParameter,
    DbFindingStatus,
    DbRankEntry,
    DegradationIndex,
    DbSeriesSummary,
    LoadLevel,
    MetricRanking,
    MetricStatsBundle,
    ParameterImpactSummary,
    TrajectoryPoint,
    TrendTestResult,
)
from backend.tests.conftest import make_descriptive_stats, make_pairwise, make_test_info

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

FIXED_SECTIONS = ["Итог", "Что важно", "Надёжность вывода", "Что делать дальше"]


def _section(report, title: str):
    return next(section for section in report.sections if section.title == title)


def _all_text(report) -> str:
    texts = [report.verdict]
    for s in report.sections:
        texts.extend(s.items)
    for f in report.per_db_findings:
        texts.append(f.db_label)
        texts.append(f.status_reason)
        texts.extend(f.highlights)
        for c in f.chips:
            texts.extend([c.label, c.value])
    return " ".join(texts)


def _assert_no_uuids(report):
    text = _all_text(report)
    assert not _UUID_RE.search(text), f"UUID найден в тексте отчёта: {_UUID_RE.search(text).group()}"


# ======================================================================
# Per-test
# ======================================================================

class TestPerTestReport:
    def _gen(self):
        return PerTestReportGenerator()

    def _make_data(self, pairwise=None, descriptive_stats=None, db_key_labels=None, rankings=None):
        return {
            "test_info": make_test_info(name="Test Run"),
            "descriptive_stats": descriptive_stats or {},
            "pairwise": pairwise or [],
            "rankings": rankings or [],
            "db_key_labels": db_key_labels or {"db1": "MySQL", "db2": "PostgreSQL"},
        }

    def test_fixed_sections_and_per_db_findings(self):
        rankings = [
            MetricRanking(
                metric="throughput_mean", best_db_key="db2",
                rankings=[
                    DbRankEntry(db_key="db2", db_label="PostgreSQL", rank=1, value=120.0),
                    DbRankEntry(db_key="db1", db_label="MySQL", rank=2, value=100.0),
                ],
            ),
            MetricRanking(
                metric="latency_mean", best_db_key="db1",
                rankings=[
                    DbRankEntry(db_key="db1", db_label="MySQL", rank=1, value=40.0),
                    DbRankEntry(db_key="db2", db_label="PostgreSQL", rank=2, value=50.0),
                ],
            ),
        ]
        data = self._make_data(
            pairwise=[
                make_pairwise("db1", "db2", db_key="MySQL vs PostgreSQL", metric="throughput"),
                make_pairwise("db1", "db2", db_key="MySQL vs PostgreSQL", metric="latency_ms"),
            ],
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=45.0),
                    throughput=make_descriptive_stats(mean=100.0),
                    source="raw_samples",
                ),
                "db2": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=50.0),
                    throughput=make_descriptive_stats(mean=120.0),
                    source="raw_samples",
                ),
            },
            rankings=rankings,
        )

        report = self._gen().generate(**data)

        assert report.verdict
        assert [s.title for s in report.sections] == FIXED_SECTIONS
        assert len(report.per_db_findings) == 2

        labels = {f.db_label for f in report.per_db_findings}
        assert "MySQL" in labels
        assert "PostgreSQL" in labels

        for f in report.per_db_findings:
            assert f.status in (DbFindingStatus.GOOD, DbFindingStatus.WARNING, DbFindingStatus.CRITICAL)
            assert f.status_reason
            assert len(f.chips) > 0
            for chip in f.chips:
                assert any(u in chip.value for u in ("req/s", "ms", "%")), f"Chip без единиц: {chip.value}"

        assert len(_section(report, "Что важно").items) <= 4
        assert len(_section(report, "Что делать дальше").items) <= 3
        assert len(_section(report, "Надёжность вывода").items) <= 2

    def test_error_db_is_critical(self):
        data = self._make_data(
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=45.0),
                    throughput=make_descriptive_stats(mean=100.0),
                    error_rate=1.5,
                    source="raw_samples",
                ),
            },
            db_key_labels={"db1": "MySQL"},
        )
        report = self._gen().generate(**data)
        finding = report.per_db_findings[0]
        assert finding.status == DbFindingStatus.CRITICAL
        assert "ошибки" in finding.status_reason.lower()

    def test_stable_db_is_good(self):
        data = self._make_data(
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=45.0, std=5.0, p99=60.0, median=44.0, p50=44.0),
                    throughput=make_descriptive_stats(mean=100.0),
                    source="raw_samples",
                ),
            },
            db_key_labels={"db1": "PostgreSQL"},
        )
        report = self._gen().generate(**data)
        finding = report.per_db_findings[0]
        assert finding.status == DbFindingStatus.GOOD

    def test_high_tail_db_is_warning(self):
        data = self._make_data(
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=50.0, std=30.0, p99=200.0, median=45.0, p50=45.0),
                    source="raw_samples",
                ),
            },
            db_key_labels={"db1": "MariaDB"},
        )
        report = self._gen().generate(**data)
        finding = report.per_db_findings[0]
        assert finding.status == DbFindingStatus.WARNING
        assert "хвост" in finding.status_reason

    def test_no_uuids_in_report(self):
        data = self._make_data(
            pairwise=[
                make_pairwise(
                    str(uuid.uuid4()), str(uuid.uuid4()),
                    db_key=str(uuid.uuid4()),
                    metric="latency_ms",
                    effect_size=1.2, effect_size_label="large",
                    is_significant=True, p_value=0.001,
                    is_significant_adjusted=True, p_value_adjusted=0.003,
                ),
            ],
            descriptive_stats={
                "db1": MetricStatsBundle(
                    latency_ms=make_descriptive_stats(mean=45.0),
                    throughput=make_descriptive_stats(mean=100.0),
                    source="raw_samples",
                ),
            },
        )
        report = self._gen().generate(**data)
        _assert_no_uuids(report)

    def test_config_does_not_hide_sections(self):
        config = AnalysisReportConfig(
            include_verdict=False, include_patterns=False,
            include_recommendations=False, include_hypotheses=False,
        )
        report = self._gen().generate(**self._make_data(), config=config)
        assert [s.title for s in report.sections] == FIXED_SECTIONS

    def test_adjusted_significance_in_reliability(self):
        pairwise = [
            make_pairwise(
                "db1", "db2", db_key="MySQL vs PostgreSQL", metric="latency_ms",
                is_significant=True, p_value=0.01,
                is_significant_adjusted=False, p_value_adjusted=0.2,
                effect_size=1.1, effect_size_label="large",
            )
        ]
        report = self._gen().generate(**self._make_data(pairwise=pairwise))
        important_text = " ".join(_section(report, "Что важно").items)
        reliability_text = " ".join(_section(report, "Надёжность вывода").items)
        assert "Cohen" not in important_text
        assert "FDR" in reliability_text


# ======================================================================
# Series
# ======================================================================

class TestSeriesReport:
    def _gen(self):
        return SeriesReportGenerator()

    def _make_data(self, per_db=None, load_levels=None, tests=None, parameter_impacts=None, db_key_labels=None):
        return {
            "tests": tests or [make_test_info(name="4VU"), make_test_info(name="8VU")],
            "per_db": per_db or {},
            "load_levels": load_levels or [],
            "cross_db_ranks": [],
            "db_key_labels": db_key_labels or {"conn_pg": "PostgreSQL"},
            "parameter_impacts": parameter_impacts or [],
        }

    def _load_levels(self):
        return [
            LoadLevel(level_id="l1", virtual_users=4, iterations=100, warmup_time=0, label="4 VU", test_ids=[]),
            LoadLevel(level_id="l2", virtual_users=8, iterations=100, warmup_time=0, label="8 VU", test_ids=[]),
            LoadLevel(level_id="l3", virtual_users=16, iterations=100, warmup_time=0, label="16 VU", test_ids=[]),
        ]

    def _degraded_summary(self):
        return DbSeriesSummary(
            db_key="conn_pg", db_label="PostgreSQL",
            trajectory=[
                TrajectoryPoint(level_id="l1", load_label="4 VU", throughput_mean=100.0, latency_mean=40.0, latency_p95=70.0, latency_p99=90.0),
                TrajectoryPoint(level_id="l2", load_label="8 VU", throughput_mean=102.0, latency_mean=55.0, latency_p95=110.0, latency_p99=150.0),
                TrajectoryPoint(level_id="l3", load_label="16 VU", throughput_mean=104.0, latency_mean=70.0, latency_p95=180.0, latency_p99=260.0),
            ],
            degradation=DegradationIndex(p95_changes=[57.0, 64.0], p99_changes=[67.0, 73.0], overall_p95=60.5, overall_p99=70.0),
            stability_index=0.72,
            elasticity=0.04,
            saturation_point="l2",
            trend_tests={
                "latency_p95_spearman": TrendTestResult(statistic=1.0, p_value=0.01, direction="increasing"),
                "latency_p95_mann_kendall": TrendTestResult(statistic=1.0, p_value=0.01, direction="increasing"),
            },
            adjacent_level_tests=[
                make_pairwise(
                    "l1", "l2", db_key="conn_pg", metric="latency_ms",
                    is_significant=True, is_significant_adjusted=True,
                    p_value_adjusted=0.02, effect_size=0.9, effect_size_label="large",
                )
            ],
            descriptive_stats_by_level={
                "l1": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=40.0), throughput=make_descriptive_stats(mean=100.0), source="raw_samples"),
                "l2": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=55.0), throughput=make_descriptive_stats(mean=102.0), source="raw_samples"),
                "l3": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=70.0), throughput=make_descriptive_stats(mean=104.0), source="raw_samples"),
            },
        )

    def _stable_summary(self):
        return DbSeriesSummary(
            db_key="conn_mysql", db_label="MySQL",
            trajectory=[
                TrajectoryPoint(level_id="l1", load_label="4 VU", throughput_mean=90.0, latency_mean=30.0, latency_p95=50.0, latency_p99=60.0),
                TrajectoryPoint(level_id="l2", load_label="8 VU", throughput_mean=91.0, latency_mean=31.0, latency_p95=52.0, latency_p99=62.0),
                TrajectoryPoint(level_id="l3", load_label="16 VU", throughput_mean=92.0, latency_mean=33.0, latency_p95=55.0, latency_p99=65.0),
            ],
            degradation=DegradationIndex(p95_changes=[4.0, 5.8], p99_changes=[3.3, 4.8], overall_p95=4.9, overall_p99=4.1),
            stability_index=0.05,
            elasticity=0.8,
            trend_tests={},
            adjacent_level_tests=[],
            descriptive_stats_by_level={
                "l1": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=30.0, std=3.0, p99=40.0, median=29.0, p50=29.0), throughput=make_descriptive_stats(mean=90.0), source="raw_samples"),
                "l2": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=31.0, std=3.0, p99=41.0, median=30.0, p50=30.0), throughput=make_descriptive_stats(mean=91.0), source="raw_samples"),
                "l3": MetricStatsBundle(latency_ms=make_descriptive_stats(mean=33.0, std=3.5, p99=43.0, median=32.0, p50=32.0), throughput=make_descriptive_stats(mean=92.0), source="raw_samples"),
            },
        )

    def test_fixed_sections_and_per_db_findings(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)

        assert report.verdict
        assert [s.title for s in report.sections] == FIXED_SECTIONS
        assert len(report.per_db_findings) == 1

        finding = report.per_db_findings[0]
        assert finding.db_label == "PostgreSQL"
        assert finding.status in (DbFindingStatus.WARNING, DbFindingStatus.CRITICAL)
        assert len(finding.chips) > 0
        assert len(finding.highlights) >= 1
        assert len(finding.highlights) <= 3

    def test_degraded_db_is_critical(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)
        finding = report.per_db_findings[0]
        assert finding.status == DbFindingStatus.CRITICAL

    def test_stable_db_is_good(self):
        data = self._make_data(
            per_db={"conn_mysql": self._stable_summary()},
            load_levels=self._load_levels(),
            db_key_labels={"conn_mysql": "MySQL"},
        )
        report = self._gen().generate(**data)
        finding = report.per_db_findings[0]
        assert finding.status == DbFindingStatus.GOOD
        assert "стабильна" in finding.status_reason

    def test_multi_db_each_has_finding(self):
        data = self._make_data(
            per_db={
                "conn_pg": self._degraded_summary(),
                "conn_mysql": self._stable_summary(),
            },
            load_levels=self._load_levels(),
            db_key_labels={"conn_pg": "PostgreSQL", "conn_mysql": "MySQL"},
        )
        report = self._gen().generate(**data)
        assert len(report.per_db_findings) == 2
        statuses = {f.db_label: f.status for f in report.per_db_findings}
        assert statuses["MySQL"] == DbFindingStatus.GOOD
        assert statuses["PostgreSQL"] in (DbFindingStatus.WARNING, DbFindingStatus.CRITICAL)

    def test_chips_have_units(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)
        for f in report.per_db_findings:
            for chip in f.chips:
                has_unit = any(u in chip.value for u in ("req/s", "ms", "%"))
                has_number = any(c.isdigit() for c in chip.value)
                assert has_unit or has_number, f"Chip без единиц/чисел: {chip.label}={chip.value}"

    def test_no_uuids_anywhere(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)
        _assert_no_uuids(report)

    def test_trend_tests_grouped(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)
        important_text = " ".join(_section(report, "Что важно").items)
        assert important_text.count("Тренд роста latency") == 1
        assert "spearman" not in important_text.lower()
        assert "mann_kendall" not in important_text.lower()

    def test_section_limits(self):
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
        )
        report = self._gen().generate(**data)
        assert len(_section(report, "Что важно").items) <= 4
        assert len(_section(report, "Что делать дальше").items) <= 3
        assert len(_section(report, "Надёжность вывода").items) <= 2

    def test_multi_parameter_baseline_limitation(self):
        impact = ParameterImpactSummary(
            test_id=uuid.uuid4(), test_name="Compared", vs_baseline="Baseline",
            changed_parameters=[
                ChangedParameter(parameter="virtual_users", label="VU", baseline_value=100, compared_value=50, change_description="100→50"),
                ChangedParameter(parameter="iterations", label="Iter", baseline_value=250, compared_value=90, change_description="250→90"),
            ],
            metric_effects=[], top_insights=[], summary_text="",
        )
        data = self._make_data(
            per_db={"conn_pg": self._degraded_summary()},
            load_levels=self._load_levels(),
            parameter_impacts=[impact],
        )
        report = self._gen().generate(**data)
        all_text = " ".join(item for s in report.sections for item in s.items)
        assert "вклад каждого параметра нельзя изолировать" in all_text
