"""
Rule-based генерация аналитического отчёта.

Два генератора:
- PerTestReportGenerator: отчёт по одному прогону (сравнение СУБД)
- SeriesReportGenerator: отчёт по серии прогонов (траектории СУБД)
"""
import re
from typing import Dict, List, Optional, Tuple

from backend.comparison.schemas import (
    AnalysisReport,
    AnalysisReportConfig,
    AnalysisSection,
    ComparisonTestInfo,
    CrossDbLevelRank,
    DbFinding,
    DbFindingStatus,
    DbMetricChip,
    DbSeriesSummary,
    LoadLevel,
    MetricRanking,
    MetricStatsBundle,
    PairwiseComparison,
    ParameterImpactSummary,
)


# ---------------------------------------------------------------------------
# Общие утилиты
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


class _ReportBase:
    THROUGHPUT_PARITY_THRESHOLD = 5.0
    LATENCY_NEAR_THRESHOLD = 5.0
    LATENCY_TAIL_ALERT_THRESHOLD = 50.0
    HIGH_VARIABILITY_THRESHOLD = 0.5
    HIGH_TAIL_RATIO_THRESHOLD = 3.0
    PREDICTABLE_PERFORMANCE_THRESHOLD = 2.0
    HIGH_THROUGHPUT_THRESHOLD = 100.0
    THROUGHPUT_DROP_ALERT_THRESHOLD = 30.0
    LATENCY_SPIKE_RATIO_THRESHOLD = 5.0
    DEGRADATION_CRITICAL_THRESHOLD = 50.0
    MAX_IMPORTANT_ITEMS = 4
    MAX_ACTION_ITEMS = 3
    MAX_RELIABILITY_ITEMS = 2

    @staticmethod
    def _deduplicate(items: List[str]) -> List[str]:
        seen: set = set()
        result = []
        for item in items:
            if item and item not in seen:
                result.append(item)
                seen.add(item)
        return result

    @staticmethod
    def _limit(items: List[str], limit: int) -> List[str]:
        return items[:limit]

    @staticmethod
    def _is_significant(pair: PairwiseComparison) -> bool:
        if pair.p_value_adjusted is not None:
            return pair.is_significant_adjusted
        return pair.is_significant

    @staticmethod
    def _format_p_value(pair: PairwiseComparison) -> str:
        if pair.p_value_adjusted is not None:
            return f"p(adj) = {pair.p_value_adjusted:.4f}"
        if pair.p_value is not None:
            return f"p = {pair.p_value:.4f}"
        return "p недоступно"

    @staticmethod
    def _metric_label(metric: str) -> str:
        return {
            "latency_ms": "latency",
            "throughput": "throughput",
            "throughput_mean": "throughput",
            "latency_mean": "latency mean",
            "latency_p95": "latency p95",
            "latency_p99": "latency p99",
        }.get(metric, metric)

    @staticmethod
    def _safe_label(raw: str) -> str:
        """Заменить UUID-подобные метки на человекочитаемый fallback."""
        if _UUID_RE.fullmatch(raw.strip()):
            return "СУБД"
        return raw

    def _sections(
        self,
        verdict: str,
        facts: List[str],
        important: List[str],
        reliability: List[str],
        actions: List[str],
    ) -> List[AnalysisSection]:
        return [
            AnalysisSection(title="Итог", items=self._deduplicate([verdict] + facts)),
            AnalysisSection(title="Что важно", items=self._limit(self._deduplicate(important), self.MAX_IMPORTANT_ITEMS)),
            AnalysisSection(title="Надёжность вывода", items=self._limit(self._deduplicate(reliability), self.MAX_RELIABILITY_ITEMS)),
            AnalysisSection(title="Что делать дальше", items=self._limit(self._deduplicate(actions), self.MAX_ACTION_ITEMS)),
        ]

    def _effect_size_insights(
        self,
        pairwise: List[PairwiseComparison],
        label_overrides: Optional[Dict[str, str]] = None,
        limit: int = 3,
    ) -> List[str]:
        insights = []
        label_overrides = label_overrides or {}
        candidates = [
            p for p in pairwise
            if self._is_significant(p) and p.effect_size is not None and p.effect_size_label in ("medium", "large")
        ]
        candidates.sort(key=lambda p: abs(p.effect_size or 0), reverse=True)
        for p in candidates[:limit]:
            label = self._safe_label(label_overrides.get(p.db_key, p.db_key))
            metric_label = self._metric_label(p.metric)
            effect = "большой" if p.effect_size_label == "large" else "средний"
            insights.append(
                f"{label}: {metric_label} отличается практически значимо "
                f"(Cohen's d = {abs(p.effect_size):.2f}, {effect} эффект, {self._format_p_value(p)})."
            )
        return self._deduplicate(insights)

    def _significance_summary(self, pairwise: List[PairwiseComparison]) -> str:
        tested = [p for p in pairwise if p.p_value is not None]
        if not tested:
            return "Статистические тесты не применялись: недостаточно выборок для попарных сравнений."
        raw_sig = sum(1 for p in tested if p.is_significant)
        adjusted = [p for p in tested if p.p_value_adjusted is not None]
        if adjusted:
            adj_sig = sum(1 for p in adjusted if p.is_significant_adjusted)
            return (
                f"После FDR-коррекции значимыми остаются {adj_sig} из {len(adjusted)} "
                f"сравнений; до коррекции было {raw_sig}."
            )
        return f"Значимых сравнений до FDR-коррекции: {raw_sig} из {len(tested)}."

# ---------------------------------------------------------------------------
# Режим A: Per-test report
# ---------------------------------------------------------------------------

class PerTestReportGenerator(_ReportBase):
    """Отчёт по одному прогону: сравнение СУБД между собой."""

    def generate(
        self,
        test_info: ComparisonTestInfo,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        rankings: List[MetricRanking],
        db_key_labels: Dict[str, str],
        config: Optional[AnalysisReportConfig] = None,
    ) -> AnalysisReport:
        _ = config
        verdict = self._verdict(pairwise, rankings, db_key_labels)
        facts = self._facts(test_info, descriptive_stats, pairwise, db_key_labels)
        important = self._important(descriptive_stats, pairwise, db_key_labels)
        reliability = self._reliability(descriptive_stats, pairwise)
        actions = self._actions(descriptive_stats, pairwise, db_key_labels)
        sections = self._sections(verdict, facts, important, reliability, actions)
        findings = self._per_db_findings(descriptive_stats, pairwise, db_key_labels)

        return AnalysisReport(
            verdict=verdict,
            patterns=important,
            recommendations=actions,
            hypotheses=reliability,
            sections=sections,
            per_db_findings=findings,
        )

    # ------------------------------------------------------------------
    # Per-DB scorecards
    # ------------------------------------------------------------------

    def _per_db_findings(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[DbFinding]:
        findings: List[DbFinding] = []
        for db_key, bundle in descriptive_stats.items():
            label = self._safe_label(db_key_labels.get(db_key, db_key))
            status, reason = self._per_test_status(bundle)
            chips = self._per_test_chips(bundle)
            highlights = self._per_test_highlights(db_key, label, bundle, pairwise, db_key_labels)
            findings.append(DbFinding(
                db_key=db_key,
                db_label=label,
                status=status,
                status_reason=reason,
                chips=chips,
                highlights=highlights[:3],
            ))
        return findings

    def _per_test_status(self, bundle: MetricStatsBundle) -> Tuple[DbFindingStatus, str]:
        if bundle.error_rate and bundle.error_rate > 0:
            return DbFindingStatus.CRITICAL, f"ошибки {bundle.error_rate:.2f}%"
        latency = bundle.latency_ms
        reasons: List[str] = []
        if latency:
            if latency.median > 0 and (latency.p99 / latency.median) > self.HIGH_TAIL_RATIO_THRESHOLD:
                reasons.append(f"хвост p99/median ×{latency.p99 / latency.median:.1f}")
            if latency.mean > 0 and (latency.std / latency.mean) > self.HIGH_VARIABILITY_THRESHOLD:
                reasons.append("высокая вариативность")
        if reasons:
            return DbFindingStatus.WARNING, "; ".join(reasons)
        return DbFindingStatus.GOOD, "стабильна"

    def _per_test_chips(self, bundle: MetricStatsBundle) -> List[DbMetricChip]:
        chips: List[DbMetricChip] = []
        if bundle.throughput and bundle.throughput.mean is not None:
            chips.append(DbMetricChip(label="throughput", value=f"{bundle.throughput.mean:.0f} req/s", tone="neutral"))
        if bundle.latency_ms:
            chips.append(DbMetricChip(label="p95", value=f"{bundle.latency_ms.p95:.1f} ms", tone="neutral"))
            chips.append(DbMetricChip(label="p99", value=f"{bundle.latency_ms.p99:.1f} ms", tone="neutral"))
        if bundle.error_rate and bundle.error_rate > 0:
            chips.append(DbMetricChip(label="errors", value=f"{bundle.error_rate:.2f}%", tone="negative"))
        return chips

    def _per_test_highlights(
        self,
        db_key: str,
        label: str,
        bundle: MetricStatsBundle,
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        items: List[str] = []
        if bundle.error_rate and bundle.error_rate > 0:
            items.append(f"Ошибки запросов: {bundle.error_rate:.2f}%.")
        latency = bundle.latency_ms
        if latency:
            if latency.median > 0 and (latency.p99 / latency.median) > self.HIGH_TAIL_RATIO_THRESHOLD:
                items.append(f"Длинный хвост latency: p99/median ×{latency.p99 / latency.median:.1f}.")
            if latency.mean > 0 and (latency.std / latency.mean) > self.HIGH_VARIABILITY_THRESHOLD:
                items.append(f"Высокая вариативность (CV = {latency.std / latency.mean:.2f}).")
        relevant = [
            p for p in pairwise
            if self._is_significant(p)
            and p.effect_size is not None
            and p.effect_size_label in ("medium", "large")
            and (db_key in (p.baseline_id, p.compared_id) or db_key in p.db_key)
        ]
        for p in sorted(relevant, key=lambda x: abs(x.effect_size or 0), reverse=True)[:1]:
            effect = "большой" if p.effect_size_label == "large" else "средний"
            items.append(f"{self._metric_label(p.metric)}: {effect} эффект (d = {abs(p.effect_size or 0):.2f}).")
        return items

    # ------------------------------------------------------------------
    # Verdict / sections
    # ------------------------------------------------------------------

    def _verdict(
        self,
        pairwise: List[PairwiseComparison],
        rankings: List[MetricRanking],
        db_key_labels: Dict[str, str],
    ) -> str:
        tp_ranking = next((r for r in rankings if r.metric == "throughput_mean"), None)
        latency_ranking = next((r for r in rankings if r.metric in ("latency_mean", "latency_p95")), None)
        if tp_ranking and tp_ranking.rankings:
            best = tp_ranking.rankings[0]
            label = self._safe_label(db_key_labels.get(best.db_key, best.db_key))
            if latency_ranking and latency_ranking.rankings:
                lat_best = latency_ranking.rankings[0]
                lat_label = self._safe_label(db_key_labels.get(lat_best.db_key, lat_best.db_key))
                return (
                    f"Лидер по throughput — {label} ({best.value:.1f} req/s); "
                    f"лучшая latency у {lat_label} ({lat_best.value:.2f} мс)."
                )
            return f"Лидер по throughput — {label} ({best.value:.1f} req/s)."

        throughput_items = [p for p in pairwise if p.metric == "throughput" and p.warning is None]
        sig = [p for p in throughput_items if self._is_significant(p) and p.pct_difference is not None]
        if sig:
            best = max(sig, key=lambda p: abs(p.pct_difference or 0))
            return (
                f"Главное различие по throughput: {self._safe_label(best.db_key)}, "
                f"Δ = {abs(best.pct_difference or 0):.1f}% ({self._format_p_value(best)})."
            )

        return "Явного лидера по throughput не выявлено: ключевые различия статистически не подтверждены."

    def _facts(
        self,
        test_info: ComparisonTestInfo,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        sig_count = sum(1 for p in pairwise if self._is_significant(p))
        return [
            f"Прогон «{test_info.name}»: {len(descriptive_stats)} СУБД, {len(pairwise)} попарных сравнений, {sig_count} значимых.",
        ]

    def _important(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        patterns = self._effect_size_insights(pairwise)
        high_tail: List[str] = []
        high_variability: List[str] = []
        errors: List[str] = []
        for db_key, bundle in descriptive_stats.items():
            label = self._safe_label(db_key_labels.get(db_key, db_key))
            latency = bundle.latency_ms
            if latency:
                if latency.median > 0 and (latency.p99 / latency.median) > self.HIGH_TAIL_RATIO_THRESHOLD:
                    high_tail.append(label)
                if latency.mean > 0 and (latency.std / latency.mean) > self.HIGH_VARIABILITY_THRESHOLD:
                    high_variability.append(label)
            if bundle.error_rate and bundle.error_rate > 0:
                errors.append(f"{label} ({bundle.error_rate:.2f}%)")
        if errors:
            patterns.insert(0, f"Ошибки зафиксированы у: {', '.join(errors)}.")
        if high_tail:
            patterns.append(f"Длинный хвост latency виден у: {', '.join(high_tail)}.")
        if high_variability:
            patterns.append(f"Высокая вариативность latency у: {', '.join(high_variability)}.")
        if not patterns:
            patterns.append("Критичных паттернов не видно.")
        return self._deduplicate(patterns)

    def _reliability(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
    ) -> List[str]:
        items = [self._significance_summary(pairwise)]
        sources = sorted({bundle.source for bundle in descriptive_stats.values() if bundle.source})
        low_samples = [
            db_key for db_key, bundle in descriptive_stats.items() if bundle.sample_size_warning
        ]
        parts: List[str] = []
        if sources:
            parts.append(f"источники: {', '.join(sources)}")
        if low_samples:
            parts.append(f"малая выборка у {len(low_samples)} СУБД")
        if parts:
            items.append("; ".join(parts).capitalize() + ".")
        return items

    def _actions(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        recs: List[str] = []
        if any(bundle.error_rate and bundle.error_rate > 0 for bundle in descriptive_stats.values()):
            recs.append("Устранить ошибки запросов, затем повторить сравнение.")
        if any(
            bundle.latency_ms and bundle.latency_ms.median > 0 and (bundle.latency_ms.p99 / bundle.latency_ms.median) > self.HIGH_TAIL_RATIO_THRESHOLD
            for bundle in descriptive_stats.values()
        ):
            recs.append("Проверить p99 latency: планы запросов, блокировки, I/O.")
        if not any(self._is_significant(p) for p in pairwise):
            recs.append("Увеличить выборку или повторить прогон для уверенного выбора.")
        if not recs:
            recs.append("Сопоставить выводы с SLA и стоимостью сопровождения СУБД.")
        return self._deduplicate(recs)


# ---------------------------------------------------------------------------
# Режим B: Series report
# ---------------------------------------------------------------------------

class SeriesReportGenerator(_ReportBase):
    """Отчёт по серии прогонов: поведение СУБД при разных нагрузках."""

    def generate(
        self,
        tests: List[ComparisonTestInfo],
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        cross_db_ranks: List[CrossDbLevelRank],
        db_key_labels: Dict[str, str],
        parameter_impacts: List[ParameterImpactSummary],
        config: Optional[AnalysisReportConfig] = None,
    ) -> AnalysisReport:
        _ = config
        verdict = self._verdict(per_db, load_levels, db_key_labels)
        facts = self._facts(tests, per_db, load_levels, db_key_labels)
        important = self._important(per_db, db_key_labels)
        reliability = self._reliability(tests, per_db, parameter_impacts)
        actions = self._actions(per_db, load_levels, db_key_labels, parameter_impacts)
        sections = self._sections(verdict, facts, important, reliability, actions)
        findings = self._per_db_findings(per_db, load_levels, db_key_labels)

        return AnalysisReport(
            verdict=verdict,
            patterns=important,
            recommendations=actions,
            hypotheses=reliability,
            sections=sections,
            per_db_findings=findings,
        )

    # ------------------------------------------------------------------
    # Per-DB scorecards
    # ------------------------------------------------------------------

    def _per_db_findings(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[DbFinding]:
        findings: List[DbFinding] = []
        for dk, s in per_db.items():
            label = self._safe_label(db_key_labels.get(dk, s.db_label or dk))
            status, reason = self._series_status(s)
            chips = self._series_chips(s)
            highlights = self._series_highlights(dk, label, s, load_levels, db_key_labels)
            findings.append(DbFinding(
                db_key=dk,
                db_label=label,
                status=status,
                status_reason=reason,
                chips=chips,
                highlights=highlights[:3],
            ))
        return findings

    def _series_status(self, s: DbSeriesSummary) -> Tuple[DbFindingStatus, str]:
        has_errors = any(
            bundle.error_rate and bundle.error_rate > 0
            for bundle in s.descriptive_stats_by_level.values()
        )
        if has_errors:
            return DbFindingStatus.CRITICAL, "ошибки запросов"
        if s.degradation.overall_p95 > self.DEGRADATION_CRITICAL_THRESHOLD:
            return DbFindingStatus.CRITICAL, f"деградация p95 +{s.degradation.overall_p95:.0f}%"
        if s.saturation_point is not None and s.degradation.overall_p95 > 20:
            return DbFindingStatus.CRITICAL, "насыщение + деградация"
        reasons: List[str] = []
        if s.degradation.overall_p95 > 20:
            reasons.append(f"deg p95 +{s.degradation.overall_p95:.0f}%")
        if s.stability_index is not None and s.stability_index > 0.5:
            reasons.append(f"нестабильна (CV {s.stability_index:.2f})")
        tail_hit = any(
            b.latency_ms and b.latency_ms.median > 0 and (b.latency_ms.p99 / b.latency_ms.median) > self.HIGH_TAIL_RATIO_THRESHOLD
            for b in s.descriptive_stats_by_level.values()
        )
        if tail_hit:
            reasons.append("длинный хвост p99")
        if reasons:
            return DbFindingStatus.WARNING, "; ".join(reasons)
        return DbFindingStatus.GOOD, "стабильна и масштабируется"

    def _series_chips(self, s: DbSeriesSummary) -> List[DbMetricChip]:
        chips: List[DbMetricChip] = []
        if s.trajectory:
            last = s.trajectory[-1]
            if last.throughput_mean is not None:
                chips.append(DbMetricChip(label="peak throughput", value=f"{last.throughput_mean:.0f} req/s", tone="neutral"))
            if last.latency_p95 is not None:
                chips.append(DbMetricChip(label="p95", value=f"{last.latency_p95:.1f} ms", tone="neutral"))
        if s.degradation.overall_p95 > 0:
            tone = "negative" if s.degradation.overall_p95 > 20 else "neutral"
            chips.append(DbMetricChip(label="Δ p95", value=f"+{s.degradation.overall_p95:.0f}%", tone=tone))
        if s.elasticity is not None:
            tone = "negative" if s.elasticity < 0.3 else "positive" if s.elasticity > 0.7 else "neutral"
            chips.append(DbMetricChip(label="elasticity", value=f"{s.elasticity:.2f}", tone=tone))
        return chips

    def _series_highlights(
        self,
        dk: str,
        label: str,
        s: DbSeriesSummary,
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        items: List[str] = []
        if s.degradation.overall_p95 > 20:
            items.append(f"p95 деградация +{s.degradation.overall_p95:.0f}% по серии.")
        if s.saturation_point:
            level = next((l for l in load_levels if l.level_id == s.saturation_point), None)
            if level:
                items.append(f"Насыщение на уровне {level.label}.")
        has_latency_trend = any(
            tr.direction == "increasing" and "latency" in key
            for key, tr in s.trend_tests.items()
        )
        if has_latency_trend:
            items.append("Рост latency подтверждён трендом.")
        has_tp_trend = any(
            tr.direction == "decreasing" and "throughput" in key
            for key, tr in s.trend_tests.items()
        )
        if has_tp_trend:
            items.append("Снижение throughput подтверждено трендом.")
        if s.elasticity is not None and s.elasticity < 0.3:
            items.append(f"Слабая масштабируемость (elasticity = {s.elasticity:.2f}).")
        if s.stability_index is not None and s.stability_index > 0.5:
            items.append(f"Нестабильная траектория (CV = {s.stability_index:.2f}).")
        has_errors = any(
            bundle.error_rate and bundle.error_rate > 0
            for bundle in s.descriptive_stats_by_level.values()
        )
        if has_errors:
            items.append("Ошибки запросов на некоторых уровнях нагрузки.")
        return items

    # ------------------------------------------------------------------
    # Verdict / sections
    # ------------------------------------------------------------------

    def _verdict(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> str:
        if not per_db:
            return "Недостаточно данных для итогового вердикта."

        labels = {dk: self._safe_label(db_key_labels.get(dk, s.db_label or dk)) for dk, s in per_db.items()}

        max_tp: Dict[str, float] = {}
        for dk, s in per_db.items():
            if s.trajectory:
                last = s.trajectory[-1]
                if last.throughput_mean is not None:
                    max_tp[dk] = last.throughput_mean

        parts: List[str] = []

        if len(max_tp) >= 2:
            ranked = sorted(max_tp.items(), key=lambda x: x[1], reverse=True)
            best_dk, best_val = ranked[0]
            worst_dk, worst_val = ranked[-1]
            gap_pct = ((best_val - worst_val) / worst_val * 100) if worst_val > 0 else 0

            if gap_pct > 5:
                parts.append(
                    f"При максимальной нагрузке лидирует {labels[best_dk]} "
                    f"({best_val:.0f} req/s, на {gap_pct:.0f}% выше {labels[worst_dk]})"
                )
            else:
                lo = min(max_tp.values())
                hi = max(max_tp.values())
                parts.append(
                    f"Throughput СУБД сопоставим при максимальной нагрузке ({lo:.0f}–{hi:.0f} req/s)"
                )
        elif len(max_tp) == 1:
            dk = next(iter(max_tp))
            first_tp = next(
                (tp.throughput_mean for tp in per_db[dk].trajectory if tp.throughput_mean is not None),
                None,
            )
            if first_tp is not None:
                change = ((max_tp[dk] - first_tp) / first_tp * 100) if first_tp > 0 else 0
                direction = "рост" if change > 0 else "снижение"
                parts.append(
                    f"{labels[dk]}: throughput от {first_tp:.0f} до {max_tp[dk]:.0f} req/s "
                    f"({direction} {abs(change):.0f}%)"
                )
            else:
                parts.append(f"{labels[dk]}: throughput {max_tp[dk]:.0f} req/s при максимальной нагрузке")

        degraded = [
            (labels[dk], s.degradation.overall_p95)
            for dk, s in per_db.items()
            if s.degradation.overall_p95 > 20
        ]
        if degraded:
            worst = max(degraded, key=lambda x: x[1])
            if len(degraded) == len(per_db):
                parts.append(
                    f"Все СУБД заметно деградируют при росте нагрузки, "
                    f"сильнее всего — {worst[0]} (p95 +{worst[1]:.0f}%)"
                )
            else:
                parts.append(f"Выраженная деградация p95 у {worst[0]} (+{worst[1]:.0f}%)")

        if not parts:
            return "Серия не показывает явного лидера: различия требуют дополнительной проверки."

        return ". ".join(parts) + "."

    def _facts(
        self,
        tests: List[ComparisonTestInfo],
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        saturated = self._saturation_items(per_db, load_levels, db_key_labels)
        facts = [f"Серия: {len(tests)} прогонов, {len(per_db)} СУБД, {len(load_levels)} уровней нагрузки."]
        if saturated:
            if len(saturated) == len(per_db):
                earliest = min(saturated, key=lambda x: (x[2].virtual_users, x[2].iterations))
                facts.append(f"Насыщение у всех СУБД; раньше всех — {earliest[1]} ({earliest[2].label}).")
            else:
                facts.append("Насыщение: " + ", ".join(f"{name} ({level.label})" for _, name, level in saturated) + ".")
        return facts

    def _important(
        self,
        per_db: Dict[str, DbSeriesSummary],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        patterns: List[str] = []
        labels = {dk: self._safe_label(db_key_labels.get(dk, s.db_label or dk)) for dk, s in per_db.items()}
        degraded_p95 = [
            (labels[dk], s.degradation.overall_p95)
            for dk, s in per_db.items()
            if s.degradation.overall_p95 > 20
        ]
        degraded_p99 = [
            (labels[dk], s.degradation.overall_p99)
            for dk, s in per_db.items()
            if s.degradation.overall_p99 > 30
        ]
        latency_trend = [
            labels[dk]
            for dk, s in per_db.items()
            if any(tr.direction == "increasing" and "latency" in key for key, tr in s.trend_tests.items())
        ]
        throughput_trend = [
            labels[dk]
            for dk, s in per_db.items()
            if any(tr.direction == "decreasing" and "throughput" in key for key, tr in s.trend_tests.items())
        ]
        if degraded_p95:
            worst = max(degraded_p95, key=lambda item: item[1])
            names = ", ".join(name for name, _ in degraded_p95)
            patterns.append(f"p95 деградирует у: {names}; сильнее — {worst[0]} (+{worst[1]:.0f}%).")
        patterns.extend(self._effect_size_insights(self._all_adjacent(per_db), labels, limit=2))
        if degraded_p99:
            worst = max(degraded_p99, key=lambda item: item[1])
            patterns.append(f"p99-хвост растёт у {worst[0]} (+{worst[1]:.0f}%).")
        if latency_trend:
            patterns.append(f"Тренд роста latency подтверждён у: {', '.join(latency_trend)}.")
        if throughput_trend:
            patterns.append(f"Тренд снижения throughput у: {', '.join(throughput_trend)}.")
        if not patterns:
            patterns.append("Критичных паттернов по серии не видно.")
        return self._deduplicate(patterns)

    def _reliability(
        self,
        tests: List[ComparisonTestInfo],
        per_db: Dict[str, DbSeriesSummary],
        parameter_impacts: List[ParameterImpactSummary],
    ) -> List[str]:
        all_adjacent = self._all_adjacent(per_db)
        items = [self._significance_summary(all_adjacent)]
        multi_param = [p for p in parameter_impacts if len(p.changed_parameters) > 1]
        if multi_param:
            items.append(
                "В baseline одновременно менялись несколько параметров; "
                "вклад каждого параметра нельзя изолировать."
            )
        else:
            source_values = sorted({
                bundle.source
                for summary in per_db.values()
                for bundle in summary.descriptive_stats_by_level.values()
                if bundle.source
            })
            if source_values:
                items.append(f"Источники: {', '.join(source_values)}; {len(tests)} прогонов.")
        return self._deduplicate(items)

    def _actions(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
        parameter_impacts: List[ParameterImpactSummary],
    ) -> List[str]:
        actions: List[str] = []
        if any(s.degradation.overall_p95 > 20 for s in per_db.values()):
            actions.append("Проверить блокировки, пул соединений и I/O на уровнях деградации.")
        if any(len(p.changed_parameters) > 1 for p in parameter_impacts):
            actions.append("Повторить baseline с одним параметром за раз для изоляции эффекта.")
        saturated = self._saturation_items(per_db, load_levels, db_key_labels)
        if saturated:
            items = ", ".join(f"{name} после {level.label}" for _, name, level in saturated)
            actions.append(f"Не повышать нагрузку без проверки на уровнях насыщения: {items}.")
        if not actions:
            actions.append("Расширить серию дополнительными уровнями или повторами.")
        return self._deduplicate(actions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _saturation_items(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[Tuple[str, str, LoadLevel]]:
        saturated = []
        for db_key, s in per_db.items():
            label = self._safe_label(db_key_labels.get(db_key, s.db_label or db_key))
            if s.saturation_point:
                level = next((l for l in load_levels if l.level_id == s.saturation_point), None)
                if level:
                    saturated.append((db_key, label, level))
        return saturated

    @staticmethod
    def _all_adjacent(per_db: Dict[str, DbSeriesSummary]) -> List[PairwiseComparison]:
        all_adjacent = []
        for summary in per_db.values():
            all_adjacent.extend(summary.adjacent_level_tests)
        return all_adjacent
