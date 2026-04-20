"""
Rule-based генерация аналитического отчёта по сравнению тестов
"""
from typing import Dict, List, Optional, Tuple

from backend.comparison.schemas import (
    AnalysisReport,
    AnalysisReportConfig,
    AnalysisSection,
    ComparisonTraits,
    ComparisonType,
    ComparisonResult,
    MetricStatsBundle,
)


class ComparisonReportGenerator:
    """Генератор текстового аналитического отчёта без ML/AI"""

    THROUGHPUT_PARITY_THRESHOLD = 5.0
    LATENCY_NEAR_THRESHOLD = 5.0
    LATENCY_TAIL_ALERT_THRESHOLD = 50.0
    HIGH_VARIABILITY_THRESHOLD = 0.5
    HIGH_TAIL_RATIO_THRESHOLD = 3.0
    PREDICTABLE_PERFORMANCE_THRESHOLD = 2.0
    HIGH_THROUGHPUT_THRESHOLD = 100.0
    THROUGHPUT_DROP_ALERT_THRESHOLD = 30.0
    LATENCY_SPIKE_RATIO_THRESHOLD = 5.0
    LINEAR_SCALING_THRESHOLD = 0.9
    SEVERE_DEGRADATION_THRESHOLD = 0.5
    MIN_SCALABILITY_POINTS = 2

    def generate(self, result: ComparisonResult, config: Optional[AnalysisReportConfig] = None) -> AnalysisReport:
        """Сгенерировать полный аналитический отчёт"""
        report_config = config or AnalysisReportConfig()

        verdict = self.generate_verdict(result) if report_config.include_verdict else "Генерация вердикта отключена"
        patterns = self.analyze_patterns(result) if report_config.include_patterns else []
        recommendations = self.generate_recommendations(result) if report_config.include_recommendations else []
        hypotheses = self.generate_hypotheses(result) if report_config.include_hypotheses else []

        sections = []

        executive_summary = self._generate_executive_summary(result)
        if executive_summary:
            sections.append(AnalysisSection(title="Краткое резюме", items=executive_summary))

        if report_config.include_verdict:
            sections.append(AnalysisSection(title="Основной вердикт", items=[verdict]))

        if result.parameter_impacts:
            param_items = self._generate_parameter_impact_section(result)
            if param_items:
                sections.append(AnalysisSection(title="Влияние параметров конфигурации", items=param_items))

        if report_config.include_patterns:
            sections.append(AnalysisSection(title="Выявленные паттерны", items=patterns))

        effect_insights = self._generate_effect_size_insights(result)
        if effect_insights:
            sections.append(AnalysisSection(title="Практическая значимость различий", items=effect_insights))

        if report_config.include_recommendations:
            sections.append(AnalysisSection(title="Рекомендации", items=recommendations))
        if report_config.include_hypotheses:
            sections.append(AnalysisSection(title="Возможные причины различий", items=hypotheses))

        conclusion = self._generate_conclusion(result)
        if conclusion:
            sections.append(AnalysisSection(title="Заключение", items=conclusion))

        return AnalysisReport(
            verdict=verdict,
            patterns=patterns,
            recommendations=recommendations,
            hypotheses=hypotheses,
            sections=sections,
        )

    def _get_traits(self, result: ComparisonResult) -> ComparisonTraits:
        """Get traits, falling back to defaults when absent."""
        return result.traits or ComparisonTraits()

    def generate_verdict(self, result: ComparisonResult) -> str:
        """Сгенерировать основной вердикт сравнения"""
        traits = self._get_traits(result)
        if traits.multiple_dbs and traits.same_load_params:
            return self._generate_cross_database_verdict(result)
        if not traits.same_load_params:
            return self._generate_config_comparison_verdict(result)
        if traits.is_temporal:
            return self._generate_temporal_verdict(result)
        return self._generate_cross_database_verdict(result)

    def _generate_cross_database_verdict(self, result: ComparisonResult) -> str:
        """Сгенерировать вердикт для прямого сравнения СУБД"""
        throughput_items = [
            item for item in result.pairwise_comparisons
            if item.metric == "throughput" and item.warning is None
        ]

        if not throughput_items:
            return "Недостаточно данных для итогового вердикта по пропускной способности"

        parity_candidates = []
        leaders = []

        for item in throughput_items:
            baseline_test = self._get_test_name(result, item.baseline_test_id)
            compared_test = self._get_test_name(result, item.compared_test_id)
            pct_diff = item.pct_difference

            if pct_diff is None:
                continue

            if abs(pct_diff) < self.THROUGHPUT_PARITY_THRESHOLD and not item.is_significant:
                parity_candidates.append(
                    f"{item.db_key}: системы показали практически идентичную пропускную способность "
                    f"(разница {abs(pct_diff):.1f}% находится в пределах погрешности)"
                )
                continue

            if abs(pct_diff) >= self.THROUGHPUT_PARITY_THRESHOLD and item.is_significant:
                winner = compared_test if pct_diff > 0 else baseline_test
                loser = baseline_test if pct_diff > 0 else compared_test
                leaders.append(
                    f"{item.db_key}: безоговорочный лидер по пропускной способности — {winner}, "
                    f"опередивший {loser} на {abs(pct_diff):.1f}%"
                )

        if leaders:
            return " ".join(leaders)

        if parity_candidates:
            return " ".join(parity_candidates)

        significant_items = [item for item in throughput_items if item.is_significant and item.pct_difference is not None]
        if significant_items:
            best_item = max(significant_items, key=lambda item: abs(item.pct_difference or 0))
            baseline_test = self._get_test_name(result, best_item.baseline_test_id)
            compared_test = self._get_test_name(result, best_item.compared_test_id)
            if (best_item.pct_difference or 0) > 0:
                return (
                    f"{compared_test} показывает более высокую пропускную способность относительно {baseline_test} "
                    f"на {abs(best_item.pct_difference or 0):.1f}%"
                )
            return (
                f"{baseline_test} показывает более высокую пропускную способность относительно {compared_test} "
                f"на {abs(best_item.pct_difference or 0):.1f}%"
            )

        return "Статистически значимых различий по пропускной способности не обнаружено"

    def _generate_config_comparison_verdict(self, result: ComparisonResult) -> str:
        """Verdict for tests with differing load parameters (scalability or config_comparison)."""
        traits = self._get_traits(result)

        scalability_reports = self._build_scalability_reports(result)
        if scalability_reports:
            ranked = sorted(
                scalability_reports,
                key=lambda item: (
                    item["pattern_rank"],
                    item["efficiency_tail"] if item["efficiency_tail"] is not None else -1.0,
                ),
                reverse=True,
            )
            return ranked[0]["verdict"]

        if traits.multiple_dbs:
            mixed_report = self._build_mixed_scaling_report(result)
            if mixed_report:
                return mixed_report

        return (
            "Тесты выполнены с различными параметрами нагрузки. "
            "Для итогового выбора ориентируйтесь на нормализованные метрики throughput_per_thread и scaling efficiency"
        )

    def _generate_temporal_verdict(self, result: ComparisonResult) -> str:
        """Сгенерировать вердикт для temporal-сравнения"""
        throughput_items = [
            item for item in result.pairwise_comparisons
            if item.metric == "throughput" and item.warning is None and item.pct_difference is not None
        ]
        latency_items = [
            item for item in result.pairwise_comparisons
            if item.metric == "latency_ms" and item.warning is None and item.pct_difference is not None
        ]

        if not throughput_items and not latency_items:
            return "Недостаточно данных, чтобы оценить изменение производительности во времени"

        best_throughput = max(throughput_items, key=lambda item: abs(item.pct_difference or 0), default=None)
        best_latency = max(latency_items, key=lambda item: abs(item.pct_difference or 0), default=None)

        if best_throughput and best_throughput.is_significant and (best_throughput.pct_difference or 0) > 0:
            return (
                f"Зафиксировано улучшение производительности: throughput вырос на "
                f"{abs(best_throughput.pct_difference or 0):.1f}% "
                f"(p={best_throughput.p_value:.4f})"
            )

        if best_latency and best_latency.is_significant and (best_latency.pct_difference or 0) > 0:
            return (
                f"Обнаружена регрессия latency: среднее время ответа выросло на "
                f"{abs(best_latency.pct_difference or 0):.1f}% "
                f"(p={best_latency.p_value:.4f})"
            )

        return "Явных статистически значимых изменений производительности во времени не обнаружено"

    def analyze_patterns(self, result: ComparisonResult) -> List[str]:
        """Выявить паттерны производительности и стабильности"""
        patterns = []
        baseline_id = str(result.baseline_id)

        for test in result.tests:
            test_id = str(test.id)
            bundles = result.descriptive_stats.get(test_id, {})
            for db_key, bundle in bundles.items():
                patterns.extend(self._analyze_bundle_patterns(test.name, db_key, bundle))

                if test_id == baseline_id:
                    continue

                baseline_bundle = result.descriptive_stats.get(baseline_id, {}).get(db_key)
                if baseline_bundle:
                    tail_pattern = self._analyze_latency_tail_rule(
                        baseline_test_name=self._get_test_name(result, result.baseline_id),
                        compared_test_name=test.name,
                        db_key=db_key,
                        baseline_bundle=baseline_bundle,
                        compared_bundle=bundle,
                    )
                    if tail_pattern:
                        patterns.append(tail_pattern)

        traits = self._get_traits(result)
        if not traits.same_load_params:
            patterns.extend(self._analyze_scalability_patterns(result))
            if traits.multiple_dbs:
                patterns.extend(self._analyze_mixed_patterns(result))
        if traits.is_temporal:
            patterns.extend(self._analyze_temporal_patterns(result))

        if not patterns:
            patterns.append("Явно выраженных паттернов деградации или нестабильности не обнаружено")

        return self._deduplicate(patterns)

    def generate_recommendations(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать практические рекомендации по использованию результатов"""
        recommendations = []

        for test in result.tests:
            bundles = result.descriptive_stats.get(str(test.id), {})
            for db_key, bundle in bundles.items():
                recommendations.extend(self._generate_bundle_recommendations(db_key, bundle))

        if result.warnings:
            recommendations.append(
                "Перед принятием архитектурного решения повторите сравнение после устранения предупреждений о нехватке данных"
            )

        traits = self._get_traits(result)
        if not traits.same_load_params:
            recommendations.extend(self._generate_scalability_recommendations(result))
            if traits.multiple_dbs:
                recommendations.extend(self._generate_mixed_recommendations(result))
        if traits.is_temporal:
            recommendations.extend(self._generate_temporal_recommendations(result))

        if not recommendations:
            recommendations.append("Проведите дополнительные прогоны, чтобы повысить статистическую надёжность вывода")

        return self._deduplicate(recommendations)

    def generate_hypotheses(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать эвристические гипотезы о причинах различий"""
        hypotheses = []
        baseline_name = self._get_test_name(result, result.baseline_id)
        baseline_scenarios = self._collect_test_scenarios(result, result.baseline_id)

        for item in result.pairwise_comparisons:
            if item.warning or item.pct_difference is None:
                continue

            compared_name = self._get_test_name(result, item.compared_test_id)
            lower_db_key = item.db_key.lower()

            if item.metric == "throughput" and abs(item.pct_difference) >= self.THROUGHPUT_DROP_ALERT_THRESHOLD:
                hypotheses.append(
                    f"{item.db_key}: возможная причина — заметное изменение throughput может указывать на contention, "
                    f"блокировки или I/O bottleneck под нагрузкой"
                )

            if item.metric == "latency_ms" and item.baseline_mean and item.compared_mean:
                ratio = max(item.baseline_mean, item.compared_mean) / max(min(item.baseline_mean, item.compared_mean), 0.001)
                if ratio >= self.LATENCY_SPIKE_RATIO_THRESHOLD:
                    hypotheses.append(
                        f"{item.db_key}: возможная причина — резкие скачки latency могут быть связаны с checkpoint-операциями, "
                        f"сетевыми задержками или всплесками конкуренции за ресурсы"
                    )

            if "postgres" in lower_db_key and self._is_write_heavy_scenario(baseline_scenarios) and item.is_significant:
                winner_name = compared_name if (item.pct_difference or 0) > 0 and item.metric == "throughput" else baseline_name
                if "post" in winner_name.lower() or "post" in lower_db_key:
                    hypotheses.append(
                        "Возможная причина: PostgreSQL использует более продвинутый механизм MVCC, "
                        "который лучше справляется с высокой конкурентностью на запись"
                    )

            if "mysql" in lower_db_key and self._is_read_heavy_scenario(baseline_scenarios) and item.is_significant:
                winner_name = compared_name if (item.pct_difference or 0) > 0 and item.metric == "throughput" else baseline_name
                if "mysql" in winner_name.lower() or "mysql" in lower_db_key:
                    hypotheses.append(
                        "Возможная причина: MySQL/InnoDB эффективно обрабатывает простые чтения, "
                        "в том числе за счёт кластерных индексов и предсказуемых PK lookup"
                    )

        traits = self._get_traits(result)
        if not traits.same_load_params:
            hypotheses.extend(self._generate_scalability_hypotheses(result))

        if not hypotheses:
            hypotheses.append(
                "Явных эвристических гипотез не сформировано: различия могут требовать дополнительной диагностики планов запросов, блокировок и системных метрик"
            )

        return self._deduplicate(hypotheses)

    def _analyze_bundle_patterns(self, test_name: str, db_key: str, bundle: MetricStatsBundle) -> List[str]:
        """Проанализировать паттерны внутри одного набора метрик"""
        patterns = []
        latency = bundle.latency_ms

        if latency:
            median_value = latency.median if latency.median else 0
            mean_value = latency.mean if latency.mean else 0

            if median_value > 0 and (latency.p99 / median_value) > self.HIGH_TAIL_RATIO_THRESHOLD:
                patterns.append(
                    f"{test_name}/{db_key}: высокий p99/median — есть выбросы latency и длинный хвост распределения"
                )

            if mean_value > 0 and (latency.std / mean_value) > self.HIGH_VARIABILITY_THRESHOLD:
                patterns.append(
                    f"{test_name}/{db_key}: высокая вариативность latency — производительность нестабильна"
                )

            if latency.p99 < 10 and latency.mean < 5:
                patterns.append(
                    f"{test_name}/{db_key}: отличная latency для OLTP-нагрузок"
                )

        if bundle.error_rate and bundle.error_rate > 0:
            patterns.append(
                f"{test_name}/{db_key}: есть ошибки — {bundle.error_rate:.2f}% запросов завершились неуспешно"
            )

        return patterns

    def _analyze_latency_tail_rule(
        self,
        baseline_test_name: str,
        compared_test_name: str,
        db_key: str,
        baseline_bundle: MetricStatsBundle,
        compared_bundle: MetricStatsBundle,
    ) -> Optional[str]:
        """Сравнить медиану и p99 для выявления деградации хвоста"""
        baseline_latency = baseline_bundle.latency_ms
        compared_latency = compared_bundle.latency_ms

        if not baseline_latency or not compared_latency:
            return None

        baseline_p50 = baseline_latency.p50
        compared_p50 = compared_latency.p50
        baseline_p99 = baseline_latency.p99
        compared_p99 = compared_latency.p99

        if baseline_p50 <= 0 or compared_p50 <= 0 or baseline_p99 <= 0 or compared_p99 <= 0:
            return None

        p50_diff_pct = abs(((compared_p50 - baseline_p50) / baseline_p50) * 100)
        p99_diff_pct = abs(((compared_p99 - baseline_p99) / baseline_p99) * 100)

        if p50_diff_pct <= self.LATENCY_NEAR_THRESHOLD and p99_diff_pct >= self.LATENCY_TAIL_ALERT_THRESHOLD:
            better_test = baseline_test_name if baseline_p99 < compared_p99 else compared_test_name
            worse_test = compared_test_name if better_test == baseline_test_name else baseline_test_name
            return (
                f"{db_key}: {better_test} демонстрирует более стабильное время ответа. "
                f"При близкой медиане {worse_test} испытывает заметную деградацию по p99, "
                f"что часто связано с блокировками или неоптимальным планом выполнения"
            )

        return None

    def _generate_bundle_recommendations(self, db_key: str, bundle: MetricStatsBundle) -> List[str]:
        """Сгенерировать рекомендации на основе метрик одной системы"""
        recommendations = []
        latency = bundle.latency_ms
        throughput = bundle.throughput

        if throughput and throughput.mean > self.HIGH_THROUGHPUT_THRESHOLD:
            recommendations.append(
                f"{db_key}: подходит для high-throughput сценариев"
            )

        if latency and latency.p50 > 0 and (latency.p99 / latency.p50) < self.PREDICTABLE_PERFORMANCE_THRESHOLD:
            recommendations.append(
                f"{db_key}: производительность предсказуема — подходит для production-нагрузок"
            )

        if "postgres" in db_key.lower() and latency and latency.p99 < 20:
            recommendations.append(
                f"{db_key}: PostgreSQL показывает хорошую latency на текущем сценарии"
            )

        if "mysql" in db_key.lower() and throughput and throughput.mean > 150:
            recommendations.append(
                f"{db_key}: MySQL демонстрирует высокий throughput — хорошо подходит для read-heavy нагрузки"
            )

        if bundle.error_rate and bundle.error_rate > 0:
            recommendations.append(
                f"{db_key}: сначала устраните ошибки, затем повторите сравнение — сейчас вывод по производительности ограниченно надёжен"
            )

        return recommendations

    def _analyze_scalability_patterns(self, result: ComparisonResult) -> List[str]:
        """Выявить паттерны масштабируемости по нормализованным метрикам"""
        patterns = []
        for report in self._build_scalability_reports(result):
            patterns.append(report["verdict"])
        return patterns

    def _analyze_mixed_patterns(self, result: ComparisonResult) -> List[str]:
        """Выявить mixed-паттерны по уровням нагрузки"""
        report = self._build_mixed_scaling_report(result)
        return [report] if report else []

    def _analyze_temporal_patterns(self, result: ComparisonResult) -> List[str]:
        """Выявить паттерны temporal-сравнения"""
        patterns = []
        latency_items = [
            item for item in result.pairwise_comparisons
            if item.metric == "latency_ms" and item.warning is None and item.pct_difference is not None
        ]
        for item in latency_items:
            if item.is_significant and (item.pct_difference or 0) > self.LATENCY_TAIL_ALERT_THRESHOLD:
                patterns.append(
                    f"{item.db_key}: наблюдается выраженная временная деградация latency относительно baseline"
                )
        return patterns

    def _generate_scalability_recommendations(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать рекомендации для анализа масштабируемости"""
        recommendations = []
        for report in self._build_scalability_reports(result):
            if report["pattern"] == "linear":
                recommendations.append(
                    f"{report['db_key']}: текущая СУБД хорошо масштабируется и подходит для плавного роста нагрузки"
                )
            elif report["pattern"] == "severe_degradation":
                recommendations.append(
                    f"{report['db_key']}: перед ростом числа потоков проверьте блокировки, I/O и пул подключений"
                )
            else:
                recommendations.append(
                    f"{report['db_key']}: используйте нагрузку около {report['saturation_threads']} потоков как ориентир точки насыщения"
                )
        return recommendations

    def _generate_mixed_recommendations(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать рекомендации для mixed-сравнения"""
        report = self._build_mixed_scaling_summary(result)
        recommendations = []
        if report["crossover_threads"] is not None:
            recommendations.append(
                f"Планируйте выбор СУБД под ожидаемый уровень нагрузки: около {report['crossover_threads']} потоков происходит смена лидера"
            )
        elif report["consistent_winner"]:
            recommendations.append(
                f"{report['consistent_winner']}: показывает наилучшую нормализованную эффективность на всех доступных уровнях нагрузки"
            )
        else:
            recommendations.append(
                "Для mixed-сценария полезно добавить больше уровней нагрузки, чтобы увидеть устойчивый тренд и возможную точку пересечения"
            )
        return recommendations

    def _generate_temporal_recommendations(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать рекомендации для temporal-сравнения"""
        return [
            "Для temporal-анализа фиксируйте изменения конфигурации, версии схемы и объём данных, чтобы отделять регрессии от изменения условий теста"
        ]

    def _generate_scalability_hypotheses(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать гипотезы для mixed/scalability сценариев"""
        hypotheses = []
        for report in self._build_scalability_reports(result):
            if report["pattern"] == "severe_degradation":
                hypotheses.append(
                    f"{report['db_key']}: возможная причина — при росте числа потоков система упирается в lock contention, пул соединений или I/O"
                )
            elif report["pattern"] == "saturation":
                hypotheses.append(
                    f"{report['db_key']}: возможная причина — достигнута точка насыщения, после которой растут очереди и накладные расходы планировщика"
                )
        return hypotheses

    def _build_scalability_reports(self, result: ComparisonResult) -> List[Dict[str, object]]:
        """Построить отчёты по масштабируемости для каждой СУБД"""
        reports: List[Dict[str, object]] = []
        for db_key in self._collect_all_db_keys(result):
            points = self._collect_normalized_points(result, db_key)
            if len(points) < self.MIN_SCALABILITY_POINTS:
                continue

            points.sort(key=lambda item: item["threads"])
            efficiencies = [point["scaling_efficiency"] for point in points if point["scaling_efficiency"] is not None]
            if not efficiencies:
                continue

            first_point = points[0]
            last_point = points[-1]
            max_throughput = max(point["throughput_abs"] or 0 for point in points)
            saturation_threads = self._find_saturation_point(points)
            efficiency_tail = efficiencies[-1]

            if min(efficiencies) > self.LINEAR_SCALING_THRESHOLD:
                pattern = "linear"
                verdict = (
                    f"{db_key} демонстрирует близкое к линейному масштабирование: throughput вырос "
                    f"с {first_point['throughput_abs']:.1f} до {last_point['throughput_abs']:.1f} req/s "
                    f"при росте нагрузки с {first_point['threads']} до {last_point['threads']} потоков, "
                    f"эффективность держится на уровне {efficiency_tail * 100:.0f}% от идеальной"
                )
                pattern_rank = 3
            elif efficiency_tail < self.SEVERE_DEGRADATION_THRESHOLD:
                pattern = "severe_degradation"
                verdict = (
                    f"{db_key} теряет эффективность под нагрузкой: throughput на поток снизился "
                    f"с {first_point['throughput_per_thread']:.2f} до {last_point['throughput_per_thread']:.2f} req/s/thread, "
                    f"а p99 latency вырос с {first_point['latency_p99']:.1f} до {last_point['latency_p99']:.1f} мс"
                )
                pattern_rank = 1
            else:
                pattern = "saturation"
                verdict = (
                    f"{db_key} достигает точки насыщения около {saturation_threads} потоков: "
                    f"после этого throughput растёт медленнее, а эффективность падает до {efficiency_tail * 100:.0f}%"
                )
                pattern_rank = 2

            reports.append(
                {
                    "db_key": db_key,
                    "points": points,
                    "pattern": pattern,
                    "verdict": verdict,
                    "saturation_threads": saturation_threads,
                    "max_throughput": max_throughput,
                    "efficiency_tail": efficiency_tail,
                    "pattern_rank": pattern_rank,
                }
            )

        return reports

    def _build_mixed_scaling_report(self, result: ComparisonResult) -> Optional[str]:
        """Построить verdict для mixed-сценария"""
        summary = self._build_mixed_scaling_summary(result)
        if summary["crossover_threads"] is not None:
            return (
                f"Выявлена точка пересечения производительности: при нагрузке ниже "
                f"{summary['crossover_threads']} потоков лучше {summary['low_winner']}, "
                f"а при более высокой нагрузке лидирует {summary['high_winner']}. "
                f"Выбор СУБД зависит от ожидаемого уровня нагрузки"
            )

        if summary["consistent_winner"]:
            return (
                f"{summary['consistent_winner']} превосходит альтернативы на всех доступных уровнях нагрузки: "
                f"среднее преимущество по нормализованному throughput составляет {summary['avg_diff']:.1f}%"
            )

        return None

    def _build_mixed_scaling_summary(self, result: ComparisonResult) -> Dict[str, object]:
        """Построить агрегированную mixed-сводку по победителям на уровнях нагрузки"""
        winner_by_threads: Dict[int, Dict[str, object]] = {}
        points_by_threads: Dict[int, List[Dict[str, object]]] = {}

        for db_key in self._collect_all_db_keys(result):
            for point in self._collect_normalized_points(result, db_key):
                points_by_threads.setdefault(point["threads"], []).append(point)

        for threads, points in points_by_threads.items():
            if len(points) < 2:
                continue
            ranked = sorted(
                points,
                key=lambda item: item["throughput_per_thread"] if item["throughput_per_thread"] is not None else -1.0,
                reverse=True,
            )
            winner_by_threads[threads] = ranked[0]

        sorted_levels = sorted(winner_by_threads.items(), key=lambda item: item[0])
        if not sorted_levels:
            return {
                "crossover_threads": None,
                "low_winner": None,
                "high_winner": None,
                "consistent_winner": None,
                "avg_diff": 0.0,
            }

        first_winner = self._db_family_label(sorted_levels[0][1]["db_key"])
        consistent = all(self._db_family_label(item[1]["db_key"]) == first_winner for item in sorted_levels)

        if consistent:
            diffs = []
            for _, points in points_by_threads.items():
                if len(points) < 2:
                    continue
                ranked = sorted(
                    points,
                    key=lambda item: item["throughput_per_thread"] if item["throughput_per_thread"] is not None else -1.0,
                    reverse=True,
                )
                best = ranked[0]["throughput_per_thread"]
                second = ranked[1]["throughput_per_thread"]
                if best is not None and second not in (None, 0):
                    diffs.append(((best - second) / second) * 100.0)

            return {
                "crossover_threads": None,
                "low_winner": None,
                "high_winner": None,
                "consistent_winner": first_winner,
                "avg_diff": sum(diffs) / len(diffs) if diffs else 0.0,
            }

        for index in range(1, len(sorted_levels)):
            previous_winner = self._db_family_label(sorted_levels[index - 1][1]["db_key"])
            current_winner = self._db_family_label(sorted_levels[index][1]["db_key"])
            if previous_winner != current_winner:
                return {
                    "crossover_threads": sorted_levels[index][0],
                    "low_winner": previous_winner,
                    "high_winner": current_winner,
                    "consistent_winner": None,
                    "avg_diff": 0.0,
                }

        return {
            "crossover_threads": None,
            "low_winner": None,
            "high_winner": None,
            "consistent_winner": None,
            "avg_diff": 0.0,
        }

    def _collect_normalized_points(self, result: ComparisonResult, db_key: str) -> List[Dict[str, object]]:
        """Собрать нормализованные точки по конкретной СУБД"""
        points: List[Dict[str, object]] = []

        for test in result.tests:
            test_id = str(test.id)
            bundle = result.descriptive_stats.get(test_id, {}).get(db_key)
            normalized = result.normalized_metrics.get(test_id, {}).get(db_key)
            if not bundle or not normalized:
                continue

            threads = self._read_normalized_value(normalized, "threads")
            if threads is None:
                continue

            latency = bundle.latency_ms
            points.append(
                {
                    "test_id": test_id,
                    "test_name": test.name,
                    "db_key": db_key,
                    "threads": int(threads),
                    "throughput_abs": self._read_normalized_value(normalized, "throughput_abs"),
                    "throughput_per_thread": self._read_normalized_value(normalized, "throughput_per_thread"),
                    "throughput_per_second": self._read_normalized_value(normalized, "throughput_per_second"),
                    "scaling_efficiency": self._read_normalized_value(normalized, "scaling_efficiency"),
                    "latency_mean_abs": self._read_normalized_value(normalized, "latency_mean_abs"),
                    "latency_p99": latency.p99 if latency else 0.0,
                }
            )

        return points

    def _find_saturation_point(self, points: List[Dict[str, object]]) -> int:
        """Найти точку насыщения по росту throughput"""
        max_throughput = 0.0
        saturation_threads = int(points[0]["threads"])

        for point in points:
            throughput = float(point["throughput_abs"] or 0.0)
            threads = int(point["threads"])
            if throughput > max_throughput * 1.05:
                max_throughput = throughput
                saturation_threads = threads

        return saturation_threads

    def _collect_all_db_keys(self, result: ComparisonResult) -> List[str]:
        """Собрать все ключи БД из descriptive stats"""
        db_keys = []
        for bundles in result.descriptive_stats.values():
            for db_key in bundles.keys():
                if db_key not in db_keys:
                    db_keys.append(db_key)
        return db_keys

    def _db_family_label(self, db_key: str) -> str:
        """Нормализовать название семейства СУБД для mixed-отчёта"""
        lower_key = db_key.lower()
        if "post" in lower_key:
            return "PostgreSQL"
        if "mysql" in lower_key:
            return "MySQL"
        return db_key

    def _read_normalized_value(self, normalized, key: str):
        """Безопасно прочитать значение из dict или dataclass-модели"""
        if isinstance(normalized, dict):
            return normalized.get(key)
        return getattr(normalized, key, None)

    def _collect_test_scenarios(self, result: ComparisonResult, test_id) -> List[str]:
        """Собрать список сценариев для теста"""
        target_id = str(test_id)
        for test in result.tests:
            if str(test.id) == target_id:
                scenario = test.config.get("scenario")
                if scenario:
                    return [str(scenario).lower()]
        return []

    def _is_write_heavy_scenario(self, scenarios: List[str]) -> bool:
        """Определить write-heavy сценарий по имени"""
        return any(
            scenario in {"write_only", "mixed_heavy", "oltp"} or "write" in scenario
            for scenario in scenarios
        )

    def _is_read_heavy_scenario(self, scenarios: List[str]) -> bool:
        """Определить read-heavy сценарий по имени"""
        return any(
            scenario in {"read_only", "olap", "mixed_light"} or "read" in scenario
            for scenario in scenarios
        )

    def _get_test_name(self, result: ComparisonResult, test_id) -> str:
        """Получить имя теста по его ID"""
        target_id = str(test_id)
        for test in result.tests:
            if str(test.id) == target_id:
                return test.name
        return target_id

    def _generate_executive_summary(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать краткое резюме с ключевыми цифрами"""
        items = []

        test_count = len(result.tests)
        sig_count = sum(1 for p in result.pairwise_comparisons if p.is_significant)
        total_comparisons = len(result.pairwise_comparisons)

        type_labels = {
            ComparisonType.CROSS_DATABASE: "сравнение СУБД",
            ComparisonType.SCALABILITY: "анализ масштабируемости",
            ComparisonType.CONFIG_COMPARISON: "сравнение конфигураций",
            ComparisonType.TEMPORAL: "временной анализ",
            ComparisonType.GENERAL: "сравнение",
            ComparisonType.MIXED: "сравнение конфигураций",
        }
        type_label = type_labels.get(result.comparison_type, "сравнение")

        items.append(
            f"Выполнено {type_label} по {test_count} тестам. "
            f"Из {total_comparisons} попарных сравнений {sig_count} показали статистически значимые различия."
        )

        best_throughput_test = None
        best_throughput_val = -1.0
        best_latency_test = None
        best_latency_val = float("inf")

        for test in result.tests:
            bundles = result.descriptive_stats.get(str(test.id), {})
            for db_key, bundle in bundles.items():
                if bundle.throughput and bundle.throughput.mean > best_throughput_val:
                    best_throughput_val = bundle.throughput.mean
                    best_throughput_test = test.name
                if bundle.latency_ms and bundle.latency_ms.mean < best_latency_val:
                    best_latency_val = bundle.latency_ms.mean
                    best_latency_test = test.name

        if best_throughput_test:
            items.append(
                f"Лучший throughput: «{best_throughput_test}» — {best_throughput_val:.1f} req/s."
            )
        if best_latency_test:
            items.append(
                f"Лучшая latency: «{best_latency_test}» — {best_latency_val:.2f} мс (среднее)."
            )

        large_effects = [
            p for p in result.pairwise_comparisons
            if p.effect_size_label in ("large", "medium") and p.is_significant
        ]
        if large_effects:
            best = max(large_effects, key=lambda p: abs(p.effect_size or 0))
            baseline_name = self._get_test_name(result, best.baseline_test_id)
            compared_name = self._get_test_name(result, best.compared_test_id)
            metric_label = "latency" if best.metric == "latency_ms" else best.metric
            items.append(
                f"Наиболее выраженное различие по {metric_label} между «{baseline_name}» и «{compared_name}»: "
                f"Cohen's d = {abs(best.effect_size or 0):.2f} ({best.effect_size_label}), "
                f"разница {abs(best.pct_difference or 0):.1f}%."
            )

        return items

    def _generate_parameter_impact_section(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать секцию влияния параметров из parameter_impacts"""
        items = []
        for impact_summary in result.parameter_impacts:
            if impact_summary.summary_text:
                items.append(impact_summary.summary_text)
        return items

    def _generate_effect_size_insights(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать описания практической значимости на основе effect size и CI"""
        insights = []

        for p in result.pairwise_comparisons:
            if not p.is_significant or p.effect_size is None:
                continue

            baseline_name = self._get_test_name(result, p.baseline_test_id)
            compared_name = self._get_test_name(result, p.compared_test_id)
            metric_label = "latency" if p.metric == "latency_ms" else p.metric
            db_label = p.db_key

            if p.effect_size_label == "large":
                ci_text = ""
                if p.ci_lower is not None and p.ci_upper is not None:
                    unit = "мс" if p.metric == "latency_ms" else "req/s"
                    ci_text = f" С 95% уверенностью разница составляет от {p.ci_lower:.2f} до {p.ci_upper:.2f} {unit}."
                insights.append(
                    f"{db_label} · {metric_label}: различие между «{compared_name}» и «{baseline_name}» "
                    f"практически существенно (Cohen's d = {abs(p.effect_size):.2f}, большой эффект).{ci_text}"
                )
            elif p.effect_size_label == "medium":
                insights.append(
                    f"{db_label} · {metric_label}: различие между «{compared_name}» и «{baseline_name}» "
                    f"имеет средний размер эффекта (Cohen's d = {abs(p.effect_size):.2f})."
                )
            elif p.effect_size_label == "negligible":
                insights.append(
                    f"{db_label} · {metric_label}: несмотря на статистическую значимость (p={p.p_value:.4f}), "
                    f"практический эффект пренебрежимо мал (Cohen's d = {abs(p.effect_size):.2f})."
                )

        return self._deduplicate(insights)

    def _generate_conclusion(self, result: ComparisonResult) -> List[str]:
        """Сгенерировать итоговое заключение"""
        items = []

        sig_items = [p for p in result.pairwise_comparisons if p.is_significant]
        large_items = [p for p in sig_items if p.effect_size_label in ("large", "medium")]

        if not sig_items:
            items.append(
                "Статистически значимых различий между тестами не обнаружено. "
                "Рекомендуется увеличить количество итераций или повторить тесты для повышения надёжности результатов."
            )
        elif large_items:
            items.append(
                f"Обнаружено {len(large_items)} практически значимых различий из {len(sig_items)} статистически значимых. "
                "Результаты достаточно надёжны для принятия решения о выборе конфигурации."
            )
        else:
            items.append(
                "Статистически значимые различия обнаружены, но их практический размер мал. "
                "Рекомендуется обратить внимание на другие факторы выбора: стабильность, масштабируемость, стоимость."
            )

        if result.warnings:
            items.append(
                f"В процессе анализа было получено {len(result.warnings)} предупреждений — "
                "при принятии решения учитывайте возможные ограничения данных."
            )

        return items

    def _deduplicate(self, items: List[str]) -> List[str]:
        """Удалить дубликаты с сохранением порядка"""
        unique_items = []
        seen = set()

        for item in items:
            if not item or item in seen:
                continue
            unique_items.append(item)
            seen.add(item)

        return unique_items
