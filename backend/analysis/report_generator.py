"""
Rule-based генерация аналитического отчёта.

Два генератора:
- PerTestReportGenerator: отчёт по одному прогону (сравнение СУБД)
- SeriesReportGenerator: отчёт по серии прогонов (траектории СУБД)
"""
from typing import Dict, List, Optional

from backend.comparison.schemas import (
    AnalysisReport,
    AnalysisReportConfig,
    AnalysisSection,
    ComparisonTestInfo,
    CrossDbLevelRank,
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

    @staticmethod
    def _deduplicate(items: List[str]) -> List[str]:
        seen: set = set()
        result = []
        for item in items:
            if item and item not in seen:
                result.append(item)
                seen.add(item)
        return result

    def _analyze_bundle_patterns(self, label: str, bundle: MetricStatsBundle) -> List[str]:
        patterns = []
        latency = bundle.latency_ms
        if latency:
            if latency.median > 0 and (latency.p99 / latency.median) > self.HIGH_TAIL_RATIO_THRESHOLD:
                patterns.append(f"{label}: высокий p99/median — есть выбросы latency и длинный хвост распределения")
            if latency.mean > 0 and (latency.std / latency.mean) > self.HIGH_VARIABILITY_THRESHOLD:
                patterns.append(f"{label}: высокая вариативность latency — производительность нестабильна")
            if latency.p99 < 10 and latency.mean < 5:
                patterns.append(f"{label}: отличная latency для OLTP-нагрузок")
        if bundle.error_rate and bundle.error_rate > 0:
            patterns.append(f"{label}: есть ошибки — {bundle.error_rate:.2f}% запросов завершились неуспешно")
        return patterns

    def _bundle_recommendations(self, label: str, bundle: MetricStatsBundle) -> List[str]:
        recs = []
        if bundle.throughput and bundle.throughput.mean > self.HIGH_THROUGHPUT_THRESHOLD:
            recs.append(f"{label}: подходит для high-throughput сценариев")
        if bundle.latency_ms and bundle.latency_ms.p50 > 0:
            if (bundle.latency_ms.p99 / bundle.latency_ms.p50) < self.PREDICTABLE_PERFORMANCE_THRESHOLD:
                recs.append(f"{label}: производительность предсказуема — подходит для production-нагрузок")
        if bundle.error_rate and bundle.error_rate > 0:
            recs.append(f"{label}: устраните ошибки перед выводами о производительности")
        return recs

    def _effect_size_insights(self, pairwise: List[PairwiseComparison]) -> List[str]:
        insights = []
        for p in pairwise:
            if not p.is_significant or p.effect_size is None:
                continue
            label = p.db_key
            metric_label = "latency" if p.metric == "latency_ms" else p.metric
            if p.effect_size_label == "large":
                ci = ""
                if p.ci_lower is not None and p.ci_upper is not None:
                    unit = "мс" if p.metric == "latency_ms" else "req/s"
                    ci = f" 95% CI: [{p.ci_lower:.2f}, {p.ci_upper:.2f}] {unit}."
                insights.append(
                    f"{label} · {metric_label}: различие практически существенно "
                    f"(Cohen's d = {abs(p.effect_size):.2f}, большой эффект).{ci}"
                )
            elif p.effect_size_label == "medium":
                insights.append(
                    f"{label} · {metric_label}: средний размер эффекта "
                    f"(Cohen's d = {abs(p.effect_size):.2f})."
                )
            elif p.effect_size_label == "negligible":
                insights.append(
                    f"{label} · {metric_label}: практический эффект пренебрежимо мал "
                    f"(Cohen's d = {abs(p.effect_size):.2f}), несмотря на статистическую значимость."
                )
        return self._deduplicate(insights)


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
        cfg = config or AnalysisReportConfig()

        verdict = self._verdict(pairwise, rankings, db_key_labels) if cfg.include_verdict else ""
        patterns = self._patterns(descriptive_stats, db_key_labels) if cfg.include_patterns else []
        recommendations = self._recommendations(descriptive_stats, pairwise, db_key_labels) if cfg.include_recommendations else []
        hypotheses = self._hypotheses(pairwise, db_key_labels, test_info) if cfg.include_hypotheses else []

        sections: List[AnalysisSection] = []

        summary = self._executive_summary(test_info, descriptive_stats, pairwise, rankings, db_key_labels)
        if summary:
            sections.append(AnalysisSection(title="Краткое резюме", items=summary))
        if cfg.include_verdict:
            sections.append(AnalysisSection(title="Основной вердикт", items=[verdict]))
        if cfg.include_patterns:
            sections.append(AnalysisSection(title="Выявленные паттерны", items=patterns))

        effect_insights = self._effect_size_insights(pairwise)
        if effect_insights:
            sections.append(AnalysisSection(title="Практическая значимость различий", items=effect_insights))

        if cfg.include_recommendations:
            sections.append(AnalysisSection(title="Рекомендации", items=recommendations))
        if cfg.include_hypotheses:
            sections.append(AnalysisSection(title="Возможные причины различий", items=hypotheses))

        conclusion = self._conclusion(pairwise)
        if conclusion:
            sections.append(AnalysisSection(title="Заключение", items=conclusion))

        return AnalysisReport(
            verdict=verdict,
            patterns=patterns,
            recommendations=recommendations,
            hypotheses=hypotheses,
            sections=sections,
        )

    def _verdict(
        self,
        pairwise: List[PairwiseComparison],
        rankings: List[MetricRanking],
        db_key_labels: Dict[str, str],
    ) -> str:
        tp_ranking = next((r for r in rankings if r.metric == "throughput_mean"), None)
        if tp_ranking and tp_ranking.rankings:
            best = tp_ranking.rankings[0]
            label = db_key_labels.get(best.db_key, best.db_key)
            return (
                f"Лидер по пропускной способности — {label} ({best.value:.1f} req/s). "
                f"Ранжирование основано на средних значениях throughput при одинаковой нагрузке."
            )

        throughput_items = [p for p in pairwise if p.metric == "throughput" and p.warning is None]
        sig = [p for p in throughput_items if p.is_significant and p.pct_difference is not None]
        if sig:
            best = max(sig, key=lambda p: abs(p.pct_difference or 0))
            return (
                f"Статистически значимая разница по throughput: "
                f"{best.db_key}, Δ = {abs(best.pct_difference or 0):.1f}% (p = {best.p_value:.4f})"
            )

        return "Статистически значимых различий по пропускной способности между СУБД не обнаружено"

    def _patterns(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        patterns = []
        for db_key, bundle in descriptive_stats.items():
            label = db_key_labels.get(db_key, db_key)
            patterns.extend(self._analyze_bundle_patterns(label, bundle))
        if not patterns:
            patterns.append("Явно выраженных паттернов деградации или нестабильности не обнаружено")
        return self._deduplicate(patterns)

    def _recommendations(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        recs = []
        for db_key, bundle in descriptive_stats.items():
            label = db_key_labels.get(db_key, db_key)
            recs.extend(self._bundle_recommendations(label, bundle))
        if not recs:
            recs.append("Проведите дополнительные прогоны для повышения надёжности выводов")
        return self._deduplicate(recs)

    def _hypotheses(
        self,
        pairwise: List[PairwiseComparison],
        db_key_labels: Dict[str, str],
        test_info: ComparisonTestInfo,
    ) -> List[str]:
        hyp = []
        scenario = (test_info.config.get("scenario") or "").lower()
        for p in pairwise:
            if p.warning or p.pct_difference is None:
                continue
            if p.metric == "throughput" and abs(p.pct_difference) >= self.THROUGHPUT_DROP_ALERT_THRESHOLD:
                hyp.append(
                    f"{p.db_key}: значительное различие throughput может указывать на lock contention или I/O bottleneck"
                )
            if p.metric == "latency_ms" and p.baseline_mean and p.compared_mean:
                ratio = max(p.baseline_mean, p.compared_mean) / max(min(p.baseline_mean, p.compared_mean), 0.001)
                if ratio >= self.LATENCY_SPIKE_RATIO_THRESHOLD:
                    hyp.append(
                        f"{p.db_key}: скачки latency могут быть связаны с checkpoint-операциями или всплесками конкуренции"
                    )
        if not hyp:
            hyp.append("Явных эвристических гипотез не сформировано — для диагностики рекомендуется анализ планов запросов и блокировок")
        return self._deduplicate(hyp)

    def _executive_summary(
        self,
        test_info: ComparisonTestInfo,
        descriptive_stats: Dict[str, MetricStatsBundle],
        pairwise: List[PairwiseComparison],
        rankings: List[MetricRanking],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        items = []
        db_count = len(descriptive_stats)
        sig_count = sum(1 for p in pairwise if p.is_significant)
        items.append(
            f"Анализ прогона «{test_info.name}»: {db_count} СУБД, "
            f"{len(pairwise)} попарных сравнений, {sig_count} статистически значимых."
        )

        best_tp_db = None
        best_tp_val = -1.0
        best_lat_db = None
        best_lat_val = float("inf")
        for db_key, bundle in descriptive_stats.items():
            label = db_key_labels.get(db_key, db_key)
            if bundle.throughput and bundle.throughput.mean > best_tp_val:
                best_tp_val = bundle.throughput.mean
                best_tp_db = label
            if bundle.latency_ms and bundle.latency_ms.mean < best_lat_val:
                best_lat_val = bundle.latency_ms.mean
                best_lat_db = label
        if best_tp_db:
            items.append(f"Лучший throughput: {best_tp_db} — {best_tp_val:.1f} req/s.")
        if best_lat_db:
            items.append(f"Лучшая latency: {best_lat_db} — {best_lat_val:.2f} мс (среднее).")
        return items

    def _conclusion(self, pairwise: List[PairwiseComparison]) -> List[str]:
        sig = [p for p in pairwise if p.is_significant]
        large = [p for p in sig if p.effect_size_label in ("large", "medium")]
        if not sig:
            return ["Статистически значимых различий между СУБД не обнаружено. Рекомендуется увеличить выборку."]
        if large:
            return [
                f"Обнаружено {len(large)} практически значимых различий из {len(sig)} статистически значимых. "
                "Результаты достаточно надёжны для принятия решений."
            ]
        return [
            "Статистически значимые различия обнаружены, но практический размер мал. "
            "Рекомендуется учитывать другие факторы: стабильность, масштабируемость, стоимость."
        ]


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
        cfg = config or AnalysisReportConfig()

        verdict = self._verdict(per_db, load_levels, db_key_labels) if cfg.include_verdict else ""
        patterns = self._patterns(per_db, db_key_labels) if cfg.include_patterns else []
        recommendations = self._recommendations(per_db, db_key_labels) if cfg.include_recommendations else []
        hypotheses = self._hypotheses(per_db, db_key_labels) if cfg.include_hypotheses else []

        sections: List[AnalysisSection] = []

        summary = self._executive_summary(tests, per_db, load_levels, db_key_labels)
        if summary:
            sections.append(AnalysisSection(title="Краткое резюме", items=summary))
        if cfg.include_verdict:
            sections.append(AnalysisSection(title="Основной вердикт", items=[verdict]))

        if parameter_impacts:
            pi_items = [p.summary_text for p in parameter_impacts if p.summary_text]
            if pi_items:
                sections.append(AnalysisSection(title="Влияние параметров конфигурации", items=pi_items))

        if cfg.include_patterns:
            sections.append(AnalysisSection(title="Выявленные паттерны", items=patterns))

        all_adjacent = []
        for s in per_db.values():
            all_adjacent.extend(s.adjacent_level_tests)
        effect_insights = self._effect_size_insights(all_adjacent)
        if effect_insights:
            sections.append(AnalysisSection(title="Практическая значимость различий", items=effect_insights))

        if cfg.include_recommendations:
            sections.append(AnalysisSection(title="Рекомендации", items=recommendations))
        if cfg.include_hypotheses:
            sections.append(AnalysisSection(title="Возможные причины различий", items=hypotheses))

        conclusion = self._conclusion(per_db, db_key_labels)
        if conclusion:
            sections.append(AnalysisSection(title="Заключение", items=conclusion))

        return AnalysisReport(
            verdict=verdict,
            patterns=patterns,
            recommendations=recommendations,
            hypotheses=hypotheses,
            sections=sections,
        )

    def _verdict(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> str:
        parts = []
        for db_key, s in per_db.items():
            label = db_key_labels.get(db_key, s.db_label or db_key)
            deg_text = ""
            if s.degradation.overall_p95 > 20:
                deg_text = f", выраженная деградация p95 (средний рост {s.degradation.overall_p95:.0f}%)"
            elif s.degradation.overall_p95 > 5:
                deg_text = f", умеренная деградация p95 ({s.degradation.overall_p95:.0f}%)"

            stab_text = ""
            if s.stability_index is not None:
                if s.stability_index < 0.1:
                    stab_text = ", высокая стабильность"
                elif s.stability_index > 0.5:
                    stab_text = ", низкая стабильность"

            sat_text = ""
            if s.saturation_point:
                level = next((l for l in load_levels if l.level_id == s.saturation_point), None)
                if level:
                    sat_text = f", точка насыщения при {level.label}"

            parts.append(f"{label}{deg_text}{stab_text}{sat_text}")

        if not parts:
            return "Недостаточно данных для итогового вердикта по серии"

        return "Анализ серии прогонов: " + "; ".join(parts) + "."

    def _patterns(
        self,
        per_db: Dict[str, DbSeriesSummary],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        patterns = []
        for db_key, s in per_db.items():
            label = db_key_labels.get(db_key, s.db_label or db_key)

            if s.degradation.overall_p95 > 20:
                patterns.append(f"{label}: выраженная деградация p95 при росте нагрузки (среднее изменение +{s.degradation.overall_p95:.0f}%)")
            if s.degradation.overall_p99 > 30:
                patterns.append(f"{label}: значительная деградация p99 при росте нагрузки (+{s.degradation.overall_p99:.0f}%)")

            if s.stability_index is not None and s.stability_index > 0.5:
                patterns.append(f"{label}: нестабильная производительность по уровням нагрузки (индекс устойчивости {s.stability_index:.2f})")

            if s.elasticity is not None:
                if s.elasticity > 0.9:
                    patterns.append(f"{label}: близкое к линейному масштабирование (эластичность {s.elasticity:.2f})")
                elif s.elasticity < 0.3:
                    patterns.append(f"{label}: низкая эластичность — throughput плохо масштабируется с ростом потоков ({s.elasticity:.2f})")

            for trend_key, trend in s.trend_tests.items():
                if trend.direction == "increasing" and "latency" in trend_key:
                    patterns.append(f"{label}: обнаружен статистически значимый тренд роста latency ({trend_key}, p = {trend.p_value:.4f})")
                elif trend.direction == "decreasing" and "throughput" in trend_key:
                    patterns.append(f"{label}: обнаружен тренд снижения throughput ({trend_key}, p = {trend.p_value:.4f})")

            for bundle in s.descriptive_stats_by_level.values():
                patterns.extend(self._analyze_bundle_patterns(label, bundle))

        if not patterns:
            patterns.append("Явно выраженных паттернов деградации или нестабильности не обнаружено")
        return self._deduplicate(patterns)

    def _recommendations(
        self,
        per_db: Dict[str, DbSeriesSummary],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        recs = []
        for db_key, s in per_db.items():
            label = db_key_labels.get(db_key, s.db_label or db_key)

            if s.saturation_point:
                recs.append(f"{label}: не превышайте нагрузку уровня {s.saturation_point} — после этого throughput не растёт")

            if s.degradation.overall_p95 > 20:
                recs.append(f"{label}: при повышении нагрузки проверьте блокировки, пул соединений и I/O")

            if s.elasticity is not None and s.elasticity > 0.9:
                recs.append(f"{label}: подходит для плавного масштабирования нагрузки")

            for bundle in s.descriptive_stats_by_level.values():
                recs.extend(self._bundle_recommendations(label, bundle))

        if not recs:
            recs.append("Проведите дополнительные прогоны с большим диапазоном нагрузок для повышения надёжности выводов")
        return self._deduplicate(recs)

    def _hypotheses(
        self,
        per_db: Dict[str, DbSeriesSummary],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        hyp = []
        for db_key, s in per_db.items():
            label = db_key_labels.get(db_key, s.db_label or db_key)

            if s.degradation.overall_p95 > 20:
                hyp.append(f"{label}: деградация при росте нагрузки может указывать на lock contention, I/O bottleneck или исчерпание пула соединений")

            if s.saturation_point:
                hyp.append(f"{label}: точка насыщения может быть связана с ростом очередей и накладных расходов планировщика")

            if s.elasticity is not None and s.elasticity < 0.3:
                hyp.append(f"{label}: низкая эластичность — возможно, рабочие нагрузки упираются в однопоточные участки или блокировки")

        if not hyp:
            hyp.append("Явных эвристических гипотез не сформировано — для диагностики рекомендуется анализ планов запросов, блокировок и системных метрик")
        return self._deduplicate(hyp)

    def _executive_summary(
        self,
        tests: List[ComparisonTestInfo],
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        items = []
        items.append(
            f"Серийный анализ: {len(tests)} прогонов, {len(per_db)} СУБД, {len(load_levels)} уровней нагрузки."
        )

        for db_key, s in per_db.items():
            label = db_key_labels.get(db_key, s.db_label or db_key)
            tp_vals = [tp.throughput_mean for tp in s.trajectory if tp.throughput_mean is not None]
            if tp_vals:
                items.append(f"{label}: throughput от {min(tp_vals):.1f} до {max(tp_vals):.1f} req/s по уровням нагрузки.")
            lat_vals = [tp.latency_p95 for tp in s.trajectory if tp.latency_p95 is not None]
            if lat_vals:
                items.append(f"{label}: p95 latency от {min(lat_vals):.1f} до {max(lat_vals):.1f} мс.")

        return items

    def _conclusion(
        self,
        per_db: Dict[str, DbSeriesSummary],
        db_key_labels: Dict[str, str],
    ) -> List[str]:
        items = []
        best_elasticity_db = None
        best_elasticity = -1.0
        for db_key, s in per_db.items():
            if s.elasticity is not None and s.elasticity > best_elasticity:
                best_elasticity = s.elasticity
                best_elasticity_db = db_key_labels.get(db_key, s.db_label or db_key)

        if best_elasticity_db and best_elasticity > 0.5:
            items.append(f"Лучшую масштабируемость демонстрирует {best_elasticity_db} (эластичность {best_elasticity:.2f}).")

        degradation_dbs = [
            db_key_labels.get(dk, s.db_label or dk)
            for dk, s in per_db.items()
            if s.degradation.overall_p95 > 20
        ]
        if degradation_dbs:
            items.append(f"Выраженная деградация p95 при росте нагрузки: {', '.join(degradation_dbs)}.")

        saturation_dbs = [
            db_key_labels.get(dk, s.db_label or dk)
            for dk, s in per_db.items()
            if s.saturation_point
        ]
        if saturation_dbs:
            items.append(f"Точка насыщения обнаружена для: {', '.join(saturation_dbs)}.")

        if not items:
            items.append("Для более точных выводов рекомендуется увеличить число уровней нагрузки и повторить прогоны.")

        return items
