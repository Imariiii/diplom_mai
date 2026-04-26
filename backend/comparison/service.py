"""
Сервис двухрежимного сравнительного анализа прогонов.

Два пайплайна:
- _run_per_test: внутритестовый анализ (один прогон, все пары СУБД)
- _run_series: серийный анализ (несколько прогонов, траектории по СУБД)
"""
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from backend.comparison.schemas import (
    AnalysisMode,
    AnalysisReportConfig,
    AnalysisWarning,
    BarChartPoint,
    BoxPlotPoint,
    ChangedParameter,
    ComparabilityReport,
    ComparisonRequest,
    ComparisonResult,
    ComparisonTestInfo,
    ConnectionInfo,
    CrossDbLevelRank,
    DbRankEntry,
    DbSeriesSummary,
    LoadLevel,
    MetricEffect,
    MetricRanking,
    MetricStatsBundle,
    ParameterImpactSummary,
    PairwiseComparison,
    PerTestCharts,
    PerTestResult,
    ResourceMetrics,
    ScenarioInfo,
    ScenarioQueryInfo,
    SeriesChartPoint,
    SeriesCharts,
    SeriesResult,
    ThroughputSeriesPoint,
    TrajectoryPoint,
)
from backend.comparison.statistics import (
    MIN_SAMPLE_SIZE_FOR_TEST,
    apply_fdr_correction,
    calculate_box_plot_stats,
    calculate_degradation_index,
    calculate_descriptive_stats,
    calculate_elasticity,
    calculate_stability_index,
    compare_two_samples,
    detect_saturation_point,
    mann_kendall_trend,
    spearman_correlation,
)


class ComparisonService:
    """Сервис для анализа и сравнения нагрузочных прогонов"""

    def __init__(self, repository, scenario_bundle_repository=None, connection_repository=None):
        self.repository = repository
        self.scenario_bundle_repository = scenario_bundle_repository
        self.connection_repository = connection_repository

    async def analyze(self, request: ComparisonRequest) -> ComparisonResult:
        """Главная точка входа: маршрутизация по analysis_mode."""
        if request.analysis_mode == AnalysisMode.PER_TEST:
            return await self._run_per_test(request)
        return await self._run_series(request)

    # ======================================================================
    # Режим A: внутритестовый анализ (per-test)
    # ======================================================================

    async def _run_per_test(self, request: ComparisonRequest) -> PerTestResult:
        """Один прогон — сравнение всех СУБД между собой."""
        test_id = request.test_ids[0]
        test_data = await self._load_single_test(test_id)
        test_info = await self._build_test_info(test_data)
        db_keys = self._get_test_db_keys(test_data)
        db_key_labels = self._build_db_key_labels([test_data])

        warnings: List[AnalysisWarning] = []

        if len(db_keys) < 2:
            warnings.append(AnalysisWarning(
                severity="warn", code="single_db",
                message="В прогоне только одна СУБД — попарное сравнение невозможно",
            ))

        descriptive_stats: Dict[str, MetricStatsBundle] = {}
        raw_samples: Dict[str, Dict[str, Any]] = {}
        charts = PerTestCharts()

        for db_key in db_keys:
            samples_info = await self._collect_metric_samples(str(test_id), db_key, test_data)
            bundle = self._build_metric_bundle(samples_info, warnings, test_data["name"], db_key)
            descriptive_stats[db_key] = bundle
            raw_samples[db_key] = samples_info

            label = db_key_labels.get(db_key, db_key)
            self._append_charts_per_test(charts, test_data, db_key, label, bundle, samples_info)

        pairwise = self._build_all_db_pairs(db_keys, raw_samples, db_key_labels)
        apply_fdr_correction(pairwise)

        rankings = self._build_rankings(descriptive_stats, db_key_labels)
        resource_metrics = self._collect_resource_metrics_single(test_data)

        report = None
        try:
            from backend.analysis.report_generator import PerTestReportGenerator
            generator = PerTestReportGenerator()
            report = generator.generate(
                test_info=test_info,
                descriptive_stats=descriptive_stats,
                pairwise=pairwise,
                rankings=rankings,
                db_key_labels=db_key_labels,
                config=request.report_config,
            )
        except Exception as exc:
            warnings.append(AnalysisWarning(
                severity="warn", code="report_error",
                message=f"Не удалось сгенерировать аналитический отчёт: {exc}",
            ))

        return PerTestResult(
            test=test_info,
            warnings=warnings,
            descriptive_stats=descriptive_stats,
            pairwise=pairwise,
            rankings=rankings,
            charts=charts,
            analysis_report=report,
            db_key_labels=db_key_labels,
            resource_metrics=resource_metrics,
        )

    def _build_all_db_pairs(
        self,
        db_keys: List[str],
        raw_samples: Dict[str, Dict[str, Any]],
        db_key_labels: Dict[str, str],
    ) -> List[PairwiseComparison]:
        """Построить попарные сравнения всех СУБД внутри одного прогона."""
        comparisons: List[PairwiseComparison] = []
        for i, db_a in enumerate(db_keys):
            for db_b in db_keys[i + 1:]:
                info_a = raw_samples.get(db_a, {})
                info_b = raw_samples.get(db_b, {})
                label_a = db_key_labels.get(db_a, db_a)
                label_b = db_key_labels.get(db_b, db_b)

                for metric, key in [("latency_ms", "latency_values"), ("throughput", "throughput_values")]:
                    comparisons.append(compare_two_samples(
                        a=info_a.get(key, []),
                        b=info_b.get(key, []),
                        baseline_id=label_a,
                        compared_id=label_b,
                        db_key=f"{label_a} vs {label_b}",
                        metric=metric,
                    ))
        return comparisons

    def _build_rankings(
        self,
        descriptive_stats: Dict[str, MetricStatsBundle],
        db_key_labels: Dict[str, str],
    ) -> List[MetricRanking]:
        """Ранжировать СУБД по каждой ключевой метрике."""
        metrics_spec = [
            ("throughput_mean", lambda b: b.throughput.mean if b.throughput else None, True),
            ("latency_mean", lambda b: b.latency_ms.mean if b.latency_ms else None, False),
            ("latency_p95", lambda b: b.latency_ms.p95 if b.latency_ms else None, False),
            ("latency_p99", lambda b: b.latency_ms.p99 if b.latency_ms else None, False),
            ("error_rate", lambda b: b.error_rate, False),
        ]

        rankings: List[MetricRanking] = []
        for metric_name, getter, higher_is_better in metrics_spec:
            entries: List[Tuple[str, float]] = []
            for db_key, bundle in descriptive_stats.items():
                val = getter(bundle)
                if val is not None:
                    entries.append((db_key, val))

            if not entries:
                continue

            entries.sort(key=lambda e: e[1], reverse=higher_is_better)
            rank_entries = [
                DbRankEntry(
                    db_key=db_key,
                    db_label=db_key_labels.get(db_key),
                    rank=idx + 1,
                    value=round(val, 4),
                )
                for idx, (db_key, val) in enumerate(entries)
            ]
            rankings.append(MetricRanking(
                metric=metric_name,
                rankings=rank_entries,
                best_db_key=entries[0][0],
            ))
        return rankings

    def _append_charts_per_test(
        self,
        charts: PerTestCharts,
        test_data: Dict[str, Any],
        db_key: str,
        label: str,
        bundle: MetricStatsBundle,
        samples_info: Dict[str, Any],
    ):
        """Добавить точки графиков для одной СУБД в per-test режиме."""
        charts.bar_chart.append(BarChartPoint(
            label=label,
            db_key=db_key,
            latency_mean=bundle.latency_ms.mean if bundle.latency_ms else None,
            latency_p95=bundle.latency_ms.p95 if bundle.latency_ms else None,
            latency_p99=bundle.latency_ms.p99 if bundle.latency_ms else None,
            throughput_mean=bundle.throughput.mean if bundle.throughput else None,
            error_rate=bundle.error_rate,
        ))

        latency_values = samples_info.get("latency_values", [])
        if latency_values:
            try:
                box_stats = calculate_box_plot_stats(latency_values)
                charts.box_plot.append(BoxPlotPoint(
                    label=label,
                    db_key=db_key,
                    min=box_stats["min"],
                    q1=box_stats["q1"],
                    median=box_stats["median"],
                    q3=box_stats["q3"],
                    max=box_stats["max"],
                    sample_count=int(box_stats["sample_count"]),
                ))
            except ValueError:
                pass

    # ======================================================================
    # Режим B: серийный анализ по СУБД (series)
    # ======================================================================

    async def _run_series(self, request: ComparisonRequest) -> SeriesResult:
        """Несколько прогонов — траектории СУБД при разных нагрузках."""
        unique_ids = self._normalize_test_ids(request.test_ids)
        baseline_id = self._resolve_baseline_id(unique_ids, request.baseline_id)

        tests = await self._load_tests(unique_ids)
        self._validate_tests_for_comparison(tests)

        comparability = self._build_comparability_report(tests)
        if not comparability.is_valid_for_series:
            raise ValueError(
                "Прогоны несопоставимы для серийного анализа: "
                + "; ".join(comparability.reasons)
            )

        load_levels = self._build_load_levels(tests)
        test_infos = [await self._build_test_info(t) for t in tests]
        db_key_labels = self._build_db_key_labels(tests)
        warnings: List[AnalysisWarning] = []

        all_db_keys = self._get_all_db_keys(tests)

        descriptive_stats_map: Dict[str, Dict[str, MetricStatsBundle]] = {}
        raw_samples_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        charts = SeriesCharts()

        for test_data in tests:
            tid = str(test_data["id"])
            descriptive_stats_map[tid] = {}
            raw_samples_map[tid] = {}
            for db_key in self._get_test_db_keys(test_data):
                samples_info = await self._collect_metric_samples(tid, db_key, test_data)
                bundle = self._build_metric_bundle(samples_info, warnings, test_data["name"], db_key)
                descriptive_stats_map[tid][db_key] = bundle
                raw_samples_map[tid][db_key] = samples_info

        per_db: Dict[str, DbSeriesSummary] = {}
        for db_key in all_db_keys:
            summary = self._build_db_series_summary(
                db_key=db_key,
                db_label=db_key_labels.get(db_key),
                tests=tests,
                load_levels=load_levels,
                descriptive_stats_map=descriptive_stats_map,
                raw_samples_map=raw_samples_map,
            )
            per_db[db_key] = summary
            self._fill_series_charts(charts, db_key, db_key_labels.get(db_key, db_key), summary)

        cross_db_ranks = self._build_cross_db_ranks(per_db, load_levels, db_key_labels)
        self._fill_series_bar_box(charts, tests, descriptive_stats_map, raw_samples_map, db_key_labels, load_levels)

        resource_metrics = self._collect_resource_metrics(tests)

        parameter_impacts = self._build_parameter_impact_analysis(
            tests=tests,
            baseline_id=baseline_id,
            descriptive_stats=descriptive_stats_map,
            db_key_labels=db_key_labels,
        )

        report = None
        try:
            from backend.analysis.report_generator import SeriesReportGenerator
            generator = SeriesReportGenerator()
            report = generator.generate(
                tests=test_infos,
                per_db=per_db,
                load_levels=load_levels,
                cross_db_ranks=cross_db_ranks,
                db_key_labels=db_key_labels,
                parameter_impacts=parameter_impacts,
                config=request.report_config,
            )
        except Exception as exc:
            warnings.append(AnalysisWarning(
                severity="warn", code="report_error",
                message=f"Не удалось сгенерировать аналитический отчёт: {exc}",
            ))

        return SeriesResult(
            tests=test_infos,
            baseline_id=baseline_id,
            comparability=comparability,
            load_levels=load_levels,
            per_db=per_db,
            cross_db_ranks=cross_db_ranks,
            charts=charts,
            analysis_report=report,
            db_key_labels=db_key_labels,
            parameter_impacts=parameter_impacts,
            warnings=warnings,
            resource_metrics=resource_metrics,
        )

    # ------------------------------------------------------------------
    # ComparabilityReport
    # ------------------------------------------------------------------

    def _build_comparability_report(self, tests: List[Dict[str, Any]]) -> ComparabilityReport:
        """Проверить сопоставимость прогонов для серийного анализа."""
        sigs = [self._build_workload_signature(t) for t in tests]
        reasons: List[str] = []

        scenarios = set(s.get("scenario") for s in sigs)
        same_scenario = len(scenarios) <= 1
        if not same_scenario:
            reasons.append(f"Различные сценарии: {', '.join(str(s) for s in scenarios)}")

        query_sets = set(s.get("query_ids") for s in sigs)
        same_query_ids = len(query_sets) <= 1
        if not same_query_ids:
            reasons.append("Различные наборы запросов в сценариях")

        bundle_ids = {s.get("bundle_id") for s in sigs if s.get("bundle_id")}
        if len(bundle_ids) > 1:
            reasons.append("Различные SQL bundle сценариев")

        logical_db_ids = {s.get("logical_database_id") for s in sigs if s.get("logical_database_id")}
        if len(logical_db_ids) > 1:
            reasons.append("Различные logical database")

        profile_ids = set()
        for t in tests:
            config = t.get("config", {}) or {}
            pid = config.get("resolved_profile_id") or config.get("schema_profile_id")
            profile_ids.add(pid)
        profile_ids.discard(None)
        same_schema_profile = len(profile_ids) <= 1
        if not same_schema_profile:
            reasons.append("Различные профили схемы данных")

        vu_set = set(s.get("virtual_users") for s in sigs)
        it_set = set(s.get("iterations") for s in sigs)
        wu_set = set(s.get("warmup_time") for s in sigs)
        same_load_params = len(vu_set) <= 1 and len(it_set) <= 1 and len(wu_set) <= 1

        is_valid = same_scenario and same_query_ids and len(bundle_ids) <= 1 and len(logical_db_ids) <= 1

        return ComparabilityReport(
            same_scenario=same_scenario,
            same_query_ids=same_query_ids,
            same_schema_profile=same_schema_profile,
            same_load_params=same_load_params,
            is_valid_for_series=is_valid,
            reasons=reasons,
        )

    def _build_load_levels(self, tests: List[Dict[str, Any]]) -> List[LoadLevel]:
        """Построить упорядоченный список уровней нагрузки из конфигураций прогонов."""
        level_map: Dict[str, LoadLevel] = {}
        for t in tests:
            config = t.get("config", {}) or {}
            vu = int(config.get("virtual_users", 1) or 1)
            it = int(config.get("iterations", 1) or 1)
            wu = float(config.get("warmup_time", 0) or 0)
            level_id = f"vu{vu}_it{it}_wu{int(wu)}"
            label = f"{vu} VU / {it} iter"

            if level_id not in level_map:
                level_map[level_id] = LoadLevel(
                    level_id=level_id,
                    virtual_users=vu,
                    iterations=it,
                    warmup_time=wu,
                    label=label,
                    test_ids=[],
                )
            level_map[level_id].test_ids.append(UUID(str(t["id"])))

        levels = sorted(level_map.values(), key=lambda l: (l.virtual_users, l.iterations))
        return levels

    def _build_db_series_summary(
        self,
        db_key: str,
        db_label: Optional[str],
        tests: List[Dict[str, Any]],
        load_levels: List[LoadLevel],
        descriptive_stats_map: Dict[str, Dict[str, MetricStatsBundle]],
        raw_samples_map: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> DbSeriesSummary:
        """Построить полную сводку серии для одной СУБД."""
        trajectory: List[TrajectoryPoint] = []
        stats_by_level: Dict[str, MetricStatsBundle] = {}
        adjacent_tests: List[PairwiseComparison] = []

        p95_values: List[float] = []
        p99_values: List[float] = []
        cv_values: List[float] = []
        tp_values: List[float] = []
        thread_counts: List[int] = []
        level_ids: List[str] = []

        for level in load_levels:
            tid = str(level.test_ids[0]) if level.test_ids else None
            if not tid:
                continue

            bundle = descriptive_stats_map.get(tid, {}).get(db_key)
            if not bundle:
                continue

            stats_by_level[level.level_id] = bundle

            tp_mean = bundle.throughput.mean if bundle.throughput else None
            lat_mean = bundle.latency_ms.mean if bundle.latency_ms else None
            lat_p95 = bundle.latency_ms.p95 if bundle.latency_ms else None
            lat_p99 = bundle.latency_ms.p99 if bundle.latency_ms else None
            cv = bundle.latency_ms.cv if bundle.latency_ms else None
            err = bundle.error_rate

            trajectory.append(TrajectoryPoint(
                level_id=level.level_id,
                load_label=level.label,
                throughput_mean=tp_mean,
                latency_mean=lat_mean,
                latency_p95=lat_p95,
                latency_p99=lat_p99,
                error_rate=err,
                cv=cv,
            ))

            if lat_p95 is not None:
                p95_values.append(lat_p95)
            if lat_p99 is not None:
                p99_values.append(lat_p99)
            if cv is not None:
                cv_values.append(cv)
            if tp_mean is not None:
                tp_values.append(tp_mean)
                thread_counts.append(level.virtual_users)
            level_ids.append(level.level_id)

        prev_level_tid = None
        prev_level_samples = None
        for level in load_levels:
            tid = str(level.test_ids[0]) if level.test_ids else None
            if not tid:
                continue
            curr_samples = raw_samples_map.get(tid, {}).get(db_key, {})
            if prev_level_tid and prev_level_samples and curr_samples:
                for metric, key in [("latency_ms", "latency_values"), ("throughput", "throughput_values")]:
                    adjacent_tests.append(compare_two_samples(
                        a=prev_level_samples.get(key, []),
                        b=curr_samples.get(key, []),
                        baseline_id=prev_level_tid,
                        compared_id=tid,
                        db_key=db_key,
                        metric=metric,
                    ))
            prev_level_tid = tid
            prev_level_samples = curr_samples

        apply_fdr_correction(adjacent_tests)

        degradation = calculate_degradation_index(p95_values, p99_values)
        stability = calculate_stability_index(cv_values)
        elasticity = calculate_elasticity(tp_values, thread_counts)

        saturation = detect_saturation_point(tp_values, p95_values, level_ids)

        trend_tests = {}
        if len(tp_values) >= 3:
            x_levels = list(range(len(tp_values)))
            sp_tp = spearman_correlation(x_levels, tp_values)
            if sp_tp:
                trend_tests["throughput_spearman"] = sp_tp
            mk_tp = mann_kendall_trend(tp_values)
            if mk_tp:
                trend_tests["throughput_mann_kendall"] = mk_tp

        if len(p95_values) >= 3:
            x_levels = list(range(len(p95_values)))
            sp_lat = spearman_correlation(x_levels, p95_values)
            if sp_lat:
                trend_tests["latency_p95_spearman"] = sp_lat
            mk_lat = mann_kendall_trend(p95_values)
            if mk_lat:
                trend_tests["latency_p95_mann_kendall"] = mk_lat

        return DbSeriesSummary(
            db_key=db_key,
            db_label=db_label,
            trajectory=trajectory,
            degradation=degradation,
            stability_index=stability,
            elasticity=elasticity,
            saturation_point=saturation,
            trend_tests=trend_tests,
            adjacent_level_tests=adjacent_tests,
            descriptive_stats_by_level=stats_by_level,
        )

    def _build_cross_db_ranks(
        self,
        per_db: Dict[str, DbSeriesSummary],
        load_levels: List[LoadLevel],
        db_key_labels: Dict[str, str],
    ) -> List[CrossDbLevelRank]:
        """Ранжировать СУБД по каждому уровню нагрузки и метрике."""
        ranks: List[CrossDbLevelRank] = []
        metrics_spec = [
            ("throughput_mean", lambda tp: tp.throughput_mean, True),
            ("latency_mean", lambda tp: tp.latency_mean, False),
            ("latency_p95", lambda tp: tp.latency_p95, False),
        ]

        for level in load_levels:
            for metric_name, getter, higher_is_better in metrics_spec:
                entries: List[Tuple[str, float]] = []
                for db_key, summary in per_db.items():
                    for tp in summary.trajectory:
                        if tp.level_id == level.level_id:
                            val = getter(tp)
                            if val is not None:
                                entries.append((db_key, val))
                            break

                if not entries:
                    continue

                entries.sort(key=lambda e: e[1], reverse=higher_is_better)
                rank_entries = [
                    DbRankEntry(
                        db_key=dk, db_label=db_key_labels.get(dk),
                        rank=idx + 1, value=round(v, 4),
                    )
                    for idx, (dk, v) in enumerate(entries)
                ]
                ranks.append(CrossDbLevelRank(
                    level_id=level.level_id,
                    load_label=level.label,
                    metric=metric_name,
                    rankings=rank_entries,
                ))
        return ranks

    def _fill_series_charts(
        self,
        charts: SeriesCharts,
        db_key: str,
        label: str,
        summary: DbSeriesSummary,
    ):
        """Заполнить графики серии из траектории одной СУБД."""
        for tp in summary.trajectory:
            def _pt(val):
                return SeriesChartPoint(level_id=tp.level_id, load_label=tp.load_label, value=val)

            charts.throughput_by_load.setdefault(label, []).append(_pt(tp.throughput_mean))
            charts.latency_by_load.setdefault(label, []).append(_pt(tp.latency_mean))
            charts.p95_by_load.setdefault(label, []).append(_pt(tp.latency_p95))
            charts.p99_by_load.setdefault(label, []).append(_pt(tp.latency_p99))
            charts.error_rate_by_load.setdefault(label, []).append(_pt(tp.error_rate))

    def _fill_series_bar_box(
        self,
        charts: SeriesCharts,
        tests: List[Dict[str, Any]],
        descriptive_stats_map: Dict[str, Dict[str, MetricStatsBundle]],
        raw_samples_map: Dict[str, Dict[str, Dict[str, Any]]],
        db_key_labels: Dict[str, str],
        load_levels: List[LoadLevel],
    ):
        """Добавить bar/box chart данные для серии (каждый тест×СУБД = точка)."""
        for level in load_levels:
            for tid in level.test_ids:
                tid_str = str(tid)
                test_data = None
                for t in tests:
                    if str(t["id"]) == tid_str:
                        test_data = t
                        break
                if not test_data:
                    continue

                for db_key in self._get_test_db_keys(test_data):
                    bundle = descriptive_stats_map.get(tid_str, {}).get(db_key)
                    if not bundle:
                        continue
                    db_label = db_key_labels.get(db_key, db_key)
                    bar_label = f"{level.label} · {db_label}"

                    charts.bar_chart.append(BarChartPoint(
                        label=bar_label,
                        db_key=db_key,
                        latency_mean=bundle.latency_ms.mean if bundle.latency_ms else None,
                        latency_p95=bundle.latency_ms.p95 if bundle.latency_ms else None,
                        latency_p99=bundle.latency_ms.p99 if bundle.latency_ms else None,
                        throughput_mean=bundle.throughput.mean if bundle.throughput else None,
                        error_rate=bundle.error_rate,
                    ))

                    latency_values = raw_samples_map.get(tid_str, {}).get(db_key, {}).get("latency_values", [])
                    if latency_values:
                        try:
                            box = calculate_box_plot_stats(latency_values)
                            charts.box_plot.append(BoxPlotPoint(
                                label=bar_label, db_key=db_key,
                                min=box["min"], q1=box["q1"], median=box["median"],
                                q3=box["q3"], max=box["max"],
                                sample_count=int(box["sample_count"]),
                            ))
                        except ValueError:
                            pass

    # ======================================================================
    # Общие утилиты (переиспользуются обоими режимами)
    # ======================================================================

    def _normalize_test_ids(self, test_ids: List[UUID]) -> List[UUID]:
        seen = set()
        result = []
        for tid in test_ids:
            if tid not in seen:
                result.append(tid)
                seen.add(tid)
        return result

    def _resolve_baseline_id(self, test_ids: List[UUID], baseline_id: Optional[UUID]) -> UUID:
        if baseline_id is None:
            return test_ids[0]
        if baseline_id not in test_ids:
            raise ValueError("Baseline-прогон должен входить в список сравниваемых прогонов")
        return baseline_id

    async def _load_single_test(self, test_id: UUID) -> Dict[str, Any]:
        test_data = await self.repository.get_test_run_with_results(str(test_id))
        if not test_data:
            raise ValueError(f"Прогон {test_id} не найден")
        return test_data

    async def _load_tests(self, test_ids: List[UUID]) -> List[Dict[str, Any]]:
        tests = []
        for tid in test_ids:
            test_data = await self.repository.get_test_run_with_results(str(tid))
            if not test_data:
                raise ValueError(f"Прогон {tid} не найден")
            tests.append(test_data)
        return tests

    def _validate_tests_for_comparison(self, tests: List[Dict[str, Any]]):
        for t in tests:
            if t.get("status") != "completed":
                raise ValueError(f"Прогон {t.get('id')} не завершён")

        logical_db_ids = set()
        for t in tests:
            ldb = t.get("logical_database_id")
            if ldb:
                logical_db_ids.add(str(ldb))
        if len(logical_db_ids) > 1:
            raise ValueError("Все прогоны должны принадлежать одной логической базе данных")

    def _build_workload_signature(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        config = test_data.get("config", {}) or {}
        results = test_data.get("results", []) or []
        snapshot = config.get("resolved_bundle_snapshot") or {}
        snapshot_queries = snapshot.get("queries") or []
        if snapshot_queries:
            query_ids = sorted([
                f"{query.get('query_type') or ''}:{query.get('sql_template') or ''}"
                for query in snapshot_queries
            ])
        else:
            query_ids = sorted([r.get("query_id") or "" for r in results])
        return {
            "scenario": config.get("scenario"),
            "iterations": config.get("iterations"),
            "virtual_users": config.get("virtual_users"),
            "warmup_time": config.get("warmup_time"),
            "db_types": tuple(sorted(config.get("db_types", []) or [])),
            "bundle_id": config.get("resolved_bundle_id") or config.get("bundle_id"),
            "profile_id": config.get("resolved_profile_id") or config.get("schema_profile_id"),
            "logical_database_id": test_data.get("logical_database_id") or config.get("logical_database_id"),
            "query_ids": tuple(query_ids),
        }

    def _get_test_db_keys(self, test_data: Dict[str, Any]) -> List[str]:
        keys = []
        for result in test_data.get("results", []) or []:
            metrics = result.get("metrics", {}) or {}
            db_key = (
                metrics.get("connection_key")
                or metrics.get("db_name")
                or result.get("db_type")
            )
            if db_key and db_key not in keys:
                keys.append(db_key)
        return keys

    def _get_all_db_keys(self, tests: List[Dict[str, Any]]) -> List[str]:
        all_keys = []
        seen = set()
        for t in tests:
            for k in self._get_test_db_keys(t):
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        return all_keys

    # ------------------------------------------------------------------
    # Сбор метрик (общий для обоих режимов)
    # ------------------------------------------------------------------

    async def _collect_metric_samples(
        self, test_id: str, db_key: str, test_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        metric_samples = []
        get_metric_samples = getattr(self.repository, "get_metric_samples", None)
        if callable(get_metric_samples):
            try:
                metric_samples = await get_metric_samples(test_id)
            except Exception as exc:
                print(f"[COMPARISON] Ошибка получения raw samples для {test_id}: {exc}")

        filtered_raw_samples = self._filter_metric_samples(metric_samples, db_key)
        filtered_raw_samples = self._filter_warmup_samples(filtered_raw_samples, test_data)
        latency_values = self._extract_latency_values(filtered_raw_samples)
        throughput_values = self._extract_throughput_values(filtered_raw_samples)

        aggregate_metrics = self._find_result_metrics(test_data, db_key)
        db_type = self._resolve_db_type(test_data, db_key, aggregate_metrics)
        latency_source = "metric_samples" if latency_values else None
        throughput_source = "metric_samples" if throughput_values else None

        if not latency_values or not throughput_values:
            series_points = await self._load_time_series(test_id, db_type, db_key)
            if not latency_values:
                latency_values = [
                    p.get("response_time") for p in series_points
                    if p.get("response_time") is not None
                ]
                if latency_values:
                    latency_source = "time_series"
            if not throughput_values:
                throughput_values = [
                    p.get("throughput") for p in series_points
                    if p.get("throughput") is not None
                ]
                if throughput_values:
                    throughput_source = "time_series"

        if not latency_values and aggregate_metrics:
            latency_source = "aggregated_metrics"
        if not throughput_values and aggregate_metrics:
            throughput_source = "aggregated_metrics"

        return {
            "latency_values": latency_values,
            "throughput_values": throughput_values,
            "aggregate_metrics": aggregate_metrics,
            "latency_source": latency_source,
            "throughput_source": throughput_source,
            "source": self._resolve_data_source(
                latency_source, throughput_source,
                filtered_raw_samples, latency_values, throughput_values,
            ),
        }

    @staticmethod
    def _filter_warmup_samples(
        samples: List[Dict[str, Any]], test_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        config = test_data.get("config", {}) or {}
        warmup_seconds = 0
        try:
            warmup_seconds = float(config.get("warmup_time", 0) or 0)
        except (TypeError, ValueError):
            pass

        if warmup_seconds <= 0 or not samples:
            return samples

        started_at_str = test_data.get("started_at")
        if not started_at_str:
            return samples

        from datetime import datetime, timedelta, timezone

        try:
            if isinstance(started_at_str, datetime):
                started_at = started_at_str
            else:
                started_at = datetime.fromisoformat(str(started_at_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return samples

        cutoff = started_at + timedelta(seconds=warmup_seconds)

        filtered = []
        for sample in samples:
            ts = sample.get("timestamp")
            if ts is None:
                filtered.append(sample)
                continue
            try:
                if isinstance(ts, datetime):
                    sample_ts = ts
                elif isinstance(ts, str):
                    sample_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    filtered.append(sample)
                    continue

                if sample_ts.tzinfo is None:
                    sample_ts = sample_ts.replace(tzinfo=timezone.utc)
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=timezone.utc)

                if sample_ts >= cutoff:
                    filtered.append(sample)
            except (ValueError, TypeError):
                filtered.append(sample)
        return filtered

    def _filter_metric_samples(self, metric_samples: List[Dict[str, Any]], db_key: str) -> List[Dict[str, Any]]:
        filtered = []
        for point in metric_samples:
            sample_db_key = (
                point.get("connection_key")
                or point.get("db_name")
                or point.get("db_type")
            )
            if sample_db_key == db_key:
                filtered.append(point)
        return filtered

    def _extract_latency_values(self, metric_samples: List[Dict[str, Any]]) -> List[float]:
        return [
            p.get("latency_ms")
            for p in metric_samples
            if p.get("sample_type") == "request_latency" and p.get("latency_ms") is not None
        ]

    def _select_throughput_samples(self, metric_samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        batch = [p for p in metric_samples if p.get("sample_type") == "throughput_window"]
        realtime = [p for p in metric_samples if p.get("sample_type") == "throughput_realtime"]
        return batch if batch else realtime

    def _extract_throughput_values(self, metric_samples: List[Dict[str, Any]]) -> List[float]:
        values = []
        for p in self._select_throughput_samples(metric_samples):
            v = p.get("throughput") or p.get("tps")
            if v is not None:
                values.append(v)
        return values

    async def _load_time_series(
        self, test_id: str, db_type: str, db_key: str = "",
    ) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        try:
            points = await self.repository.get_time_series(test_id, db_type=db_type, limit=5000)
        except Exception as exc:
            print(f"[COMPARISON] Ошибка получения time_series для {test_id}: {exc}")

        if not points:
            try:
                all_points = await self.repository.get_time_series(test_id, db_type=None, limit=5000)
                if all_points:
                    points = all_points
            except Exception:
                pass

        if points:
            return [
                {
                    "timestamp": p.get("timestamp"),
                    "throughput": p.get("throughput"),
                    "tps": p.get("tps"),
                    "response_time": p.get("response_time"),
                    "error_count": p.get("error_count"),
                }
                for p in points
            ]

        return await self._build_series_from_metric_samples(test_id, db_key)

    async def _build_series_from_metric_samples(
        self, test_id: str, db_key: str,
    ) -> List[Dict[str, Any]]:
        get_samples = getattr(self.repository, "get_metric_samples", None)
        if not callable(get_samples):
            return []
        try:
            raw = await get_samples(test_id)
        except Exception:
            return []

        series = []
        for sample in self._select_throughput_samples(raw):
            sample_key = (
                sample.get("connection_key")
                or sample.get("db_name")
                or sample.get("db_type")
            )
            if db_key and sample_key != db_key:
                continue
            tp = sample.get("throughput") or sample.get("tps")
            if tp is None:
                continue
            series.append({
                "timestamp": sample.get("timestamp"),
                "throughput": tp,
                "tps": tp,
                "response_time": sample.get("latency_ms"),
                "error_count": None,
            })
        return series

    def _resolve_db_type(self, test_data: Dict[str, Any], db_key: str, metrics: Dict[str, Any]) -> str:
        if metrics.get("db_type"):
            return metrics["db_type"]
        for result in test_data.get("results", []) or []:
            result_metrics = result.get("metrics", {}) or {}
            result_key = (
                result_metrics.get("connection_key")
                or result_metrics.get("db_name")
                or result.get("db_type")
            )
            if result_key == db_key and result.get("db_type"):
                return result["db_type"]
        lower = db_key.lower()
        if "post" in lower:
            return "postgresql"
        if "maria" in lower:
            return "mariadb"
        if "mysql" in lower:
            return "mysql"
        return db_key

    def _find_result_metrics(self, test_data: Dict[str, Any], db_key: str) -> Dict[str, Any]:
        for result in test_data.get("results", []) or []:
            metrics = result.get("metrics", {}) or {}
            result_key = (
                metrics.get("connection_key")
                or metrics.get("db_name")
                or result.get("db_type")
            )
            if result_key == db_key:
                return metrics
        return {}

    def _resolve_data_source(
        self,
        latency_source: Optional[str],
        throughput_source: Optional[str],
        raw_samples: List[Dict[str, Any]],
        latency_values: List[float],
        throughput_values: List[float],
    ) -> str:
        if latency_source and throughput_source and latency_source == throughput_source:
            return latency_source
        if latency_source or throughput_source:
            return "mixed_sources"
        if raw_samples:
            return "metric_samples"
        if latency_values or throughput_values:
            return "time_series"
        return "aggregated_metrics"

    def _build_metric_bundle(
        self,
        samples_info: Dict[str, Any],
        warnings,
        test_name: str,
        db_key: str,
    ) -> MetricStatsBundle:
        aggregate_metrics = samples_info["aggregate_metrics"]
        latency_stats = None
        throughput_stats = None
        sample_size_warning = None

        latency_values = samples_info["latency_values"]
        throughput_values = samples_info["throughput_values"]

        if latency_values:
            latency_stats = calculate_descriptive_stats(latency_values)
            if latency_stats.count < MIN_SAMPLE_SIZE_FOR_TEST:
                sample_size_warning = (
                    f"Для {test_name}/{db_key} доступно только {latency_stats.count} latency samples"
                )
        elif aggregate_metrics:
            latency_stats = self._build_stats_from_aggregates(aggregate_metrics, "latency")
            self._add_warning(
                warnings,
                f"Для {test_name}/{db_key} отсутствуют raw latency samples; использованы агрегированные метрики",
            )

        if throughput_values:
            throughput_stats = calculate_descriptive_stats(throughput_values)
        elif aggregate_metrics:
            throughput_stats = self._build_stats_from_aggregates(aggregate_metrics, "throughput")
            self._add_warning(
                warnings,
                f"Для {test_name}/{db_key} отсутствуют throughput samples; использованы агрегированные метрики",
            )

        if sample_size_warning:
            self._add_warning(warnings, sample_size_warning)

        return MetricStatsBundle(
            latency_ms=latency_stats,
            throughput=throughput_stats,
            error_rate=self._resolve_error_rate(aggregate_metrics),
            total_duration_sec=self._resolve_total_duration(aggregate_metrics),
            source=samples_info["source"],
            sample_size_warning=sample_size_warning,
        )

    @staticmethod
    def _add_warning(warnings, message: str):
        """Add a warning — works with both List[str] and List[AnalysisWarning]."""
        if warnings and isinstance(warnings, list):
            if warnings and isinstance(warnings[0], AnalysisWarning):
                warnings.append(AnalysisWarning(severity="warn", code="data_quality", message=message))
            else:
                warnings.append(message)
        elif isinstance(warnings, list):
            warnings.append(AnalysisWarning(severity="warn", code="data_quality", message=message))

    def _build_stats_from_aggregates(self, metrics: Dict[str, Any], metric_kind: str):
        if metric_kind == "latency":
            avg = float(metrics.get("avg_time_ms", 0) or 0)
            mn = float(metrics.get("min_time_ms", avg) or avg)
            mx = float(metrics.get("max_time_ms", avg) or avg)
            p50 = float(metrics.get("p50_time_ms", avg) or avg)
            p95 = float(metrics.get("p95_time_ms", avg) or avg)
            p99 = float(metrics.get("p99_time_ms", avg) or avg)
        else:
            avg = float(metrics.get("throughput", metrics.get("tps", 0)) or 0)
            mn = mx = p50 = p95 = p99 = avg
        return calculate_descriptive_stats([mn, p50, avg, p95, p99, mx])

    def _resolve_error_rate(self, metrics: Dict[str, Any]) -> Optional[float]:
        if not metrics:
            return None
        v = metrics.get("error_rate")
        return float(v) if v is not None else None

    def _resolve_total_duration(self, metrics: Dict[str, Any]) -> Optional[float]:
        if not metrics:
            return None
        if metrics.get("total_time_ms") is not None:
            return float(metrics["total_time_ms"]) / 1000.0
        tps = metrics.get("tps") or metrics.get("throughput")
        successful = metrics.get("successful")
        if tps and successful and float(tps) > 0:
            return float(successful) / float(tps)
        return None

    # ------------------------------------------------------------------
    # Test info
    # ------------------------------------------------------------------

    async def _build_test_info(self, test_data: Dict[str, Any]) -> ComparisonTestInfo:
        config = test_data.get("config", {}) or {}
        scenario_info = await self._resolve_scenario_info(config)
        connections = await self._resolve_connections(config.get("connection_ids"))
        return ComparisonTestInfo(
            id=UUID(str(test_data["id"])),
            name=test_data.get("name", "Без имени"),
            status=test_data.get("status", "unknown"),
            config=config,
            summary=test_data.get("summary"),
            started_at=test_data.get("started_at"),
            finished_at=test_data.get("finished_at"),
            scenario_info=scenario_info,
            connections=connections,
            logical_database_id=test_data.get("logical_database_id"),
            use_indexes=config.get("use_indexes"),
        )

    async def _resolve_scenario_info(self, config: Dict[str, Any]) -> Optional[ScenarioInfo]:
        if not config:
            return None

        snapshot = config.get("resolved_bundle_snapshot")
        if snapshot:
            return self._scenario_info_from_snapshot(snapshot)

        bundle_id = config.get("resolved_bundle_id") or config.get("bundle_id")
        if bundle_id and self.scenario_bundle_repository:
            try:
                bundle = await self.scenario_bundle_repository.get_bundle(bundle_id)
                if bundle:
                    return self._scenario_info_from_snapshot(bundle.to_dict())
            except Exception as exc:
                print(f"[COMPARISON] Не удалось загрузить bundle '{bundle_id}': {exc}")

        profile_id = config.get("resolved_profile_id")
        template_id = config.get("scenario_template_id") or config.get("scenario")
        if profile_id and template_id and self.scenario_bundle_repository:
            try:
                bundle = await self.scenario_bundle_repository.get_bundle_for_profile_template(
                    schema_profile_id=profile_id,
                    scenario_template_id=template_id,
                    bundle_id=bundle_id,
                )
                if bundle:
                    return self._scenario_info_from_snapshot(bundle.to_dict())
            except Exception as exc:
                print(
                    f"[COMPARISON] Не удалось разрешить active bundle для profile={profile_id}, "
                    f"template={template_id}: {exc}"
                )

        if template_id:
            return ScenarioInfo(
                name=config.get("resolved_bundle_name") or template_id,
                description=config.get("resolved_bundle_description"),
                scenario_type=template_id,
                queries=[],
            )
        return None

    def _scenario_info_from_snapshot(self, snapshot: Dict[str, Any]) -> ScenarioInfo:
        queries = [
            ScenarioQueryInfo(
                sql_template=q.get("sql_template", ""),
                query_type=q.get("query_type", "unknown"),
                weight=q.get("weight", 1),
                description=q.get("description"),
            )
            for q in snapshot.get("queries", []) or []
        ]
        return ScenarioInfo(
            name=snapshot.get("name", "Без названия"),
            description=snapshot.get("description"),
            scenario_type=snapshot.get("scenario_template_id") or snapshot.get("scenario_type", "unknown"),
            queries=queries,
        )

    async def _resolve_connections(self, connection_ids: Optional[List[str]]) -> List[ConnectionInfo]:
        if not connection_ids or not self.connection_repository:
            return []
        connections = []
        for conn_id in connection_ids:
            try:
                conn = await self.connection_repository.get_connection_by_id(conn_id)
                if conn:
                    connections.append(ConnectionInfo(
                        id=str(conn.id), name=conn.name, dbms_type=conn.dbms_type,
                        host=conn.host, port=conn.port, database=conn.database,
                    ))
            except Exception as exc:
                print(f"[COMPARISON] Не удалось разрешить подключение '{conn_id}': {exc}")
        return connections

    # ------------------------------------------------------------------
    # Labels and resources
    # ------------------------------------------------------------------

    def _build_db_key_labels(self, tests: List[Dict[str, Any]]) -> Dict[str, str]:
        labels: Dict[str, str] = {}
        for t in tests:
            for result in t.get("results", []) or []:
                metrics = result.get("metrics", {}) or {}
                db_key = (
                    metrics.get("connection_key")
                    or metrics.get("db_name")
                    or result.get("db_type")
                )
                if not db_key or db_key in labels:
                    continue
                db_name = metrics.get("db_name")
                if db_name and db_name != db_key:
                    labels[db_key] = db_name
                elif result.get("db_type"):
                    labels[db_key] = result["db_type"]
        return labels

    @staticmethod
    def _collect_resource_metrics(tests: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for t in tests:
            tk = str(t["id"])
            result[tk] = {}
            for tr in t.get("results", []) or []:
                metrics = tr.get("metrics", {}) or {}
                db_key = metrics.get("connection_key") or metrics.get("db_name") or tr.get("db_type")
                if not db_key:
                    continue
                sys_m = tr.get("system_metrics") or {}
                dbms_m = tr.get("dbms_metrics") or {}
                rm = ResourceMetrics(
                    cpu_usage=sys_m.get("cpu_usage"),
                    memory_usage_percent=sys_m.get("memory_usage_percent"),
                    disk_iops=sys_m.get("disk_iops"),
                    cache_hit_ratio=dbms_m.get("cache_hit_ratio"),
                    buffer_pool_hit_ratio=dbms_m.get("buffer_pool_hit_ratio"),
                    lock_waits=dbms_m.get("lock_waits"),
                    deadlocks=dbms_m.get("deadlocks"),
                )
                result[tk][db_key] = asdict(rm)
        return result

    @staticmethod
    def _collect_resource_metrics_single(test_data: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for tr in test_data.get("results", []) or []:
            metrics = tr.get("metrics", {}) or {}
            db_key = metrics.get("connection_key") or metrics.get("db_name") or tr.get("db_type")
            if not db_key:
                continue
            sys_m = tr.get("system_metrics") or {}
            dbms_m = tr.get("dbms_metrics") or {}
            rm = ResourceMetrics(
                cpu_usage=sys_m.get("cpu_usage"),
                memory_usage_percent=sys_m.get("memory_usage_percent"),
                disk_iops=sys_m.get("disk_iops"),
                cache_hit_ratio=dbms_m.get("cache_hit_ratio"),
                buffer_pool_hit_ratio=dbms_m.get("buffer_pool_hit_ratio"),
                lock_waits=dbms_m.get("lock_waits"),
                deadlocks=dbms_m.get("deadlocks"),
            )
            result[db_key] = asdict(rm)
        return result

    # ------------------------------------------------------------------
    # Parameter impact (серийный режим)
    # ------------------------------------------------------------------

    def _build_parameter_impact_analysis(
        self,
        tests: List[Dict[str, Any]],
        baseline_id: UUID,
        descriptive_stats: Dict[str, Dict[str, MetricStatsBundle]],
        db_key_labels: Dict[str, str],
    ) -> List[ParameterImpactSummary]:
        baseline_test = None
        for t in tests:
            if UUID(str(t["id"])) == baseline_id:
                baseline_test = t
                break
        if not baseline_test:
            return []

        baseline_config = baseline_test.get("config", {}) or {}
        baseline_key = str(baseline_id)
        baseline_stats = descriptive_stats.get(baseline_key, {})

        tracked_params = [
            ("virtual_users", "Виртуальные пользователи"),
            ("iterations", "Итерации"),
            ("use_indexes", "Индексы"),
            ("warmup_time", "Прогрев"),
        ]

        summaries: List[ParameterImpactSummary] = []
        for t in tests:
            compared_id = UUID(str(t["id"]))
            if compared_id == baseline_id:
                continue

            compared_config = t.get("config", {}) or {}
            compared_key = str(compared_id)
            compared_stats = descriptive_stats.get(compared_key, {})

            changed_params: List[ChangedParameter] = []
            for pk, pl in tracked_params:
                bv = baseline_config.get(pk)
                cv = compared_config.get(pk)
                if bv == cv:
                    continue
                changed_params.append(ChangedParameter(
                    parameter=pk, label=pl,
                    baseline_value=bv, compared_value=cv,
                    change_description=self._format_param_change(pk, bv, cv),
                ))

            metric_effects = self._compute_metric_effects(baseline_stats, compared_stats, db_key_labels)
            top_insights = self._build_top_insights(metric_effects)
            summary_text = self._format_impact_summary(
                t.get("name", ""), baseline_test.get("name", ""),
                changed_params, top_insights,
            )

            summaries.append(ParameterImpactSummary(
                test_id=compared_id,
                test_name=t.get("name", ""),
                vs_baseline=baseline_test.get("name", ""),
                changed_parameters=changed_params,
                metric_effects=metric_effects,
                top_insights=top_insights,
                summary_text=summary_text,
            ))
        return summaries

    def _format_param_change(self, param_key: str, baseline_val, compared_val) -> str:
        if param_key == "use_indexes":
            bl = "с индексами" if baseline_val else "без индексов"
            cl = "с индексами" if compared_val else "без индексов"
            return f"{bl} → {cl}"
        try:
            bn = float(baseline_val or 0)
            cn = float(compared_val or 0)
        except (TypeError, ValueError):
            return f"{baseline_val} → {compared_val}"
        if bn != 0:
            pct = ((cn - bn) / bn) * 100
            return f"{int(bn)} → {int(cn)} ({pct:+.0f}%)"
        return f"{int(bn)} → {int(cn)}"

    @staticmethod
    def _classify_magnitude(pct: float) -> str:
        abs_pct = abs(pct)
        if abs_pct < 5:
            return "negligible"
        if abs_pct < 15:
            return "small"
        if abs_pct < 30:
            return "medium"
        return "large"

    def _compute_metric_effects(
        self,
        baseline_stats: Dict[str, MetricStatsBundle],
        compared_stats: Dict[str, MetricStatsBundle],
        db_key_labels: Dict[str, str],
    ) -> List[MetricEffect]:
        effects: List[MetricEffect] = []
        common = set(baseline_stats.keys()) & set(compared_stats.keys())
        specs = [
            ("throughput", lambda b: b.throughput and b.throughput.mean, lambda b: b.throughput.mean, True),
            ("latency_mean", lambda b: b.latency_ms and b.latency_ms.mean, lambda b: b.latency_ms.mean, False),
            ("latency_p99", lambda b: b.latency_ms and b.latency_ms.p99, lambda b: b.latency_ms.p99, False),
            ("latency_cv", lambda b: b.latency_ms and b.latency_ms.cv, lambda b: b.latency_ms.cv, False),
        ]
        for dk in sorted(common):
            bb = baseline_stats[dk]
            cb = compared_stats[dk]
            for mn, has, get, hib in specs:
                if not (has(bb) and has(cb)):
                    continue
                bv, cv = get(bb), get(cb)
                if bv == 0:
                    continue
                pct = ((cv - bv) / bv) * 100
                d = "flat" if abs(pct) < 0.5 else ("up" if pct > 0 else "down")
                imp = (hib and d == "up") or (not hib and d == "down")
                effects.append(MetricEffect(
                    db_key=dk, db_label=db_key_labels.get(dk),
                    metric=mn, baseline_value=round(bv, 4), compared_value=round(cv, 4),
                    pct_change=round(pct, 2), direction=d,
                    is_improvement=imp, magnitude=self._classify_magnitude(pct),
                ))
        return effects

    @staticmethod
    def _build_top_insights(effects: List[MetricEffect], limit: int = 3) -> List[str]:
        mag_rank = {"large": 3, "medium": 2, "small": 1, "negligible": 0}
        sorted_e = sorted(effects, key=lambda e: (
            0 if not e.is_improvement else 1,
            -mag_rank.get(e.magnitude, 0),
            -abs(e.pct_change),
        ))
        labels = {"throughput": "throughput", "latency_mean": "latency mean",
                  "latency_p99": "latency p99", "latency_cv": "стабильность (CV)"}
        units = {"throughput": "req/s", "latency_mean": "мс", "latency_p99": "мс", "latency_cv": ""}
        insights: List[str] = []
        for e in sorted_e[:limit]:
            if e.magnitude == "negligible":
                continue
            db = e.db_label or e.db_key
            ml = labels.get(e.metric, e.metric)
            u = units.get(e.metric, "")
            dw = "вырос" if e.direction == "up" else "снизился"
            fb = f"{e.baseline_value:.1f}" if u else f"{e.baseline_value:.2f}"
            fc = f"{e.compared_value:.1f}" if u else f"{e.compared_value:.2f}"
            us = f" {u}" if u else ""
            insights.append(f"{db}: {ml} {dw} на {abs(e.pct_change):.1f}% ({fb} → {fc}{us})")
        return insights

    def _format_impact_summary(
        self, test_name: str, baseline_name: str,
        changed_params: List[ChangedParameter], top_insights: List[str],
    ) -> str:
        if not changed_params:
            return f"Конфигурация прогона «{test_name}» совпадает с baseline «{baseline_name}»"
        gen = {
            "virtual_users": "числа виртуальных пользователей",
            "iterations": "числа итераций",
            "use_indexes": "использования индексов",
            "warmup_time": "времени прогрева",
        }
        parts = [f"изменение {gen.get(cp.parameter, cp.parameter)} ({cp.change_description})" for cp in changed_params]
        s = f"В прогоне «{test_name}» относительно baseline «{baseline_name}»: {', '.join(parts)}."
        if top_insights:
            s += " " + "; ".join(top_insights) + "."
        return s
