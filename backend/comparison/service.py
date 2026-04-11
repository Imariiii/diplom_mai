"""
Сервис сравнительного анализа результатов тестирования
"""
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.analysis.report_generator import ComparisonReportGenerator
from backend.comparison.schemas import (
    AnalysisReportConfig,
    BarChartPoint,
    BoxPlotPoint,
    ComparisonType,
    ComparisonChartsData,
    ComparisonResult,
    ComparisonTestInfo,
    ConnectionInfo,
    MetricStatsBundle,
    NormalizedMetrics,
    ScenarioInfo,
    ScenarioQueryInfo,
    ThroughputSeriesPoint,
)
from backend.comparison.statistics import (
    MIN_SAMPLE_SIZE_FOR_TEST,
    calculate_box_plot_stats,
    calculate_descriptive_stats,
    compare_two_samples,
)


class ComparisonService:
    """Сервис для анализа и сравнения нескольких тестовых прогонов"""

    def __init__(self, repository, scenario_bundle_repository=None, connection_repository=None):
        self.repository = repository
        self.scenario_bundle_repository = scenario_bundle_repository
        self.connection_repository = connection_repository
        self.report_generator = ComparisonReportGenerator()

    async def analyze(
        self,
        test_ids: List[UUID],
        baseline_id: Optional[UUID] = None,
        report_config: Optional[AnalysisReportConfig] = None,
    ) -> ComparisonResult:
        """Выполнить сравнительный анализ по выбранным тестам"""
        unique_test_ids = self._normalize_test_ids(test_ids)
        baseline_uuid = self._resolve_baseline_id(unique_test_ids, baseline_id)

        tests = await self._load_tests(unique_test_ids)
        self._validate_tests_for_comparison(tests)
        comparison_type = self._detect_comparison_type(tests)

        warnings = []
        warnings.extend(self._collect_comparability_warnings(tests))
        warnings.extend(self._collect_comparison_type_warnings(comparison_type, tests))

        descriptive_stats = {}
        normalized_metrics = {}
        raw_samples = {}
        throughput_series = {}
        charts_data = ComparisonChartsData()

        for test_data in tests:
            test_id = test_data["id"]
            descriptive_stats[str(test_id)] = {}
            normalized_metrics[str(test_id)] = {}
            raw_samples[str(test_id)] = {}
            throughput_series[str(test_id)] = {}

            db_keys = self._get_test_db_keys(test_data)
            for db_key in db_keys:
                samples_info = await self._collect_metric_samples(str(test_id), db_key, test_data)
                metrics_bundle = self._build_metric_bundle(samples_info, warnings, test_data["name"], db_key)
                descriptive_stats[str(test_id)][db_key] = metrics_bundle
                raw_samples[str(test_id)][db_key] = samples_info

                if samples_info["latency_values"]:
                    try:
                        box_stats = calculate_box_plot_stats(samples_info["latency_values"])
                        charts_data.box_plot.append(
                            BoxPlotPoint(
                                test_id=test_id,
                                test_name=test_data["name"],
                                db_key=db_key,
                                min=box_stats["min"],
                                q1=box_stats["q1"],
                                median=box_stats["median"],
                                q3=box_stats["q3"],
                                max=box_stats["max"],
                                sample_count=int(box_stats["sample_count"]),
                            )
                        )
                    except ValueError:
                        pass

                charts_data.bar_chart.append(
                    BarChartPoint(
                        test_id=test_id,
                        test_name=test_data["name"],
                        db_key=db_key,
                        latency_mean=metrics_bundle.latency_ms.mean if metrics_bundle.latency_ms else None,
                        latency_p95=metrics_bundle.latency_ms.p95 if metrics_bundle.latency_ms else None,
                        latency_p99=metrics_bundle.latency_ms.p99 if metrics_bundle.latency_ms else None,
                        throughput_mean=metrics_bundle.throughput.mean if metrics_bundle.throughput else None,
                        error_rate=metrics_bundle.error_rate,
                    )
                )

                db_type = self._resolve_db_type(
                    test_data,
                    db_key,
                    samples_info["aggregate_metrics"],
                )
                series = await self._load_time_series(str(test_id), db_type)
                throughput_series[str(test_id)][db_key] = series
                charts_data.throughput_series[f"{test_id}:{db_key}"] = [
                    ThroughputSeriesPoint(**point) for point in series
                ]

        normalized_metrics = self._build_normalized_metrics_map(
            tests=tests,
            baseline_id=baseline_uuid,
            comparison_type=comparison_type,
            descriptive_stats=descriptive_stats,
            warnings=warnings,
        )

        pairwise_comparisons = self._build_pairwise_comparisons(
            tests=tests,
            baseline_id=baseline_uuid,
            comparison_type=comparison_type,
            raw_samples=raw_samples,
            normalized_metrics=normalized_metrics,
            warnings=warnings,
        )

        test_infos = [await self._build_test_info(test_data) for test_data in tests]
        db_key_labels = self._build_db_key_labels(tests)

        comparison_result = ComparisonResult(
            tests=test_infos,
            baseline_id=baseline_uuid,
            comparison_type=comparison_type,
            warnings=self._deduplicate_warnings(warnings),
            descriptive_stats=descriptive_stats,
            normalized_metrics=normalized_metrics,
            pairwise_comparisons=pairwise_comparisons,
            charts_data=charts_data,
            db_key_labels=db_key_labels,
        )
        comparison_result.analysis_report = self.report_generator.generate(comparison_result, report_config)
        if comparison_result.analysis_report and db_key_labels:
            self._replace_db_keys_in_report(comparison_result.analysis_report, db_key_labels)
        return comparison_result

    def _normalize_test_ids(self, test_ids: List[UUID]) -> List[UUID]:
        """Нормализовать и провалидировать список ID тестов"""
        normalized = []
        seen = set()

        for test_id in test_ids:
            if test_id in seen:
                continue
            normalized.append(test_id)
            seen.add(test_id)

        if len(normalized) < 2 or len(normalized) > 5:
            raise ValueError("Для сравнения необходимо выбрать от 2 до 5 тестов")

        return normalized

    def _resolve_baseline_id(self, test_ids: List[UUID], baseline_id: Optional[UUID]) -> UUID:
        """Определить baseline-тест"""
        if baseline_id is None:
            return test_ids[0]

        if baseline_id not in test_ids:
            raise ValueError("Baseline-тест должен входить в список сравниваемых тестов")

        return baseline_id

    async def _load_tests(self, test_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Загрузить тесты вместе с результатами"""
        tests = []

        for test_id in test_ids:
            test_data = await self.repository.get_test_run_with_results(str(test_id))
            if not test_data:
                raise ValueError(f"Тест {test_id} не найден")
            tests.append(test_data)

        return tests

    def _validate_tests_for_comparison(self, tests: List[Dict[str, Any]]):
        """Проверить базовые ограничения для сравнения"""
        for test_data in tests:
            if test_data.get("status") != "completed":
                raise ValueError(f"Тест {test_data.get('id')} не завершён и не может быть использован для сравнения")

    def _build_workload_signature(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Построить сигнатуру нагрузки для валидации сравнения"""
        config = test_data.get("config", {}) or {}
        results = test_data.get("results", []) or []
        query_ids = sorted([result.get("query_id") or "" for result in results])

        return {
            "scenario": config.get("scenario"),
            "iterations": config.get("iterations"),
            "virtual_users": config.get("virtual_users"),
            "warmup_time": config.get("warmup_time"),
            "db_types": tuple(sorted(config.get("db_types", []) or [])),
            "query_ids": tuple(query_ids),
        }

    def _detect_comparison_type(self, tests: List[Dict[str, Any]]) -> ComparisonType:
        """Автоматически определить тип сравнения"""
        workload_signatures = [self._build_workload_signature(test_data) for test_data in tests]
        signature_keys = [
            (
                signature.get("scenario"),
                signature.get("query_ids"),
                signature.get("iterations"),
                signature.get("virtual_users"),
                signature.get("warmup_time"),
            )
            for signature in workload_signatures
        ]
        db_key_sets = [
            tuple(sorted(self._get_test_db_keys(test_data)))
            for test_data in tests
        ]
        created_at_values = [test_data.get("created_at") for test_data in tests]

        same_workload = len(set(signature_keys)) == 1
        same_db_targets = len(set(db_key_sets)) == 1
        same_virtual_users = len(set(signature.get("virtual_users") for signature in workload_signatures)) == 1
        same_iterations = len(set(signature.get("iterations") for signature in workload_signatures)) == 1
        same_scenario = len(set(signature.get("scenario") for signature in workload_signatures)) == 1
        same_query_set = len(set(signature.get("query_ids") for signature in workload_signatures)) == 1

        flattened_db_keys = set()
        for db_keys in db_key_sets:
            flattened_db_keys.update(db_keys)

        unique_db_count = len(flattened_db_keys)

        if same_workload and unique_db_count > 1:
            return ComparisonType.CROSS_DATABASE

        if unique_db_count == 1 and same_scenario and same_query_set and (not same_virtual_users or not same_iterations):
            return ComparisonType.SCALABILITY

        if unique_db_count == 1 and same_workload and len(set(created_at_values)) > 1:
            return ComparisonType.TEMPORAL

        return ComparisonType.MIXED

    def _collect_comparison_type_warnings(
        self,
        comparison_type: ComparisonType,
        tests: List[Dict[str, Any]],
    ) -> List[str]:
        """Собрать предупреждения, связанные с типом сравнения"""
        warnings = []

        if comparison_type == ComparisonType.MIXED:
            warnings.append(
                "Определён mixed-сценарий: сравниваются тесты с разными конфигурациями и/или разными целевыми СУБД"
            )
        elif comparison_type == ComparisonType.SCALABILITY:
            warnings.append(
                "Определён анализ масштабируемости: для throughput и эффективности будут использоваться нормализованные метрики"
            )
        elif comparison_type == ComparisonType.TEMPORAL:
            warnings.append(
                "Определён temporal-сценарий: тесты имеют близкую конфигурацию и сравниваются как изменение производительности во времени"
            )

        if comparison_type != ComparisonType.CROSS_DATABASE:
            warnings.append(
                "Сравнение не блокируется, но интерпретация результатов требует учёта различий конфигурации"
            )

        return warnings

    def _collect_comparability_warnings(self, tests: List[Dict[str, Any]]) -> List[str]:
        """Собрать некритичные предупреждения о сравнимости"""
        warnings = []
        baseline_db_keys = set(self._get_test_db_keys(tests[0]))

        for test_data in tests[1:]:
            current_db_keys = set(self._get_test_db_keys(test_data))
            missing = baseline_db_keys - current_db_keys
            extra = current_db_keys - baseline_db_keys

            if missing:
                warnings.append(
                    f"Тест {test_data.get('name')} не содержит результаты для: {', '.join(sorted(missing))}"
                )

            if extra:
                warnings.append(
                    f"Тест {test_data.get('name')} содержит дополнительные результаты для: {', '.join(sorted(extra))}"
                )

        return warnings

    def _get_test_db_keys(self, test_data: Dict[str, Any]) -> List[str]:
        """Получить список ключей/имён СУБД внутри теста"""
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

    async def _collect_metric_samples(
        self,
        test_id: str,
        db_key: str,
        test_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Собрать данные для анализа из raw samples, time series и агрегатов"""
        metric_samples = []
        get_metric_samples = getattr(self.repository, "get_metric_samples", None)
        if callable(get_metric_samples):
            try:
                metric_samples = await get_metric_samples(test_id)
            except Exception as exc:
                print(f"[COMPARISON] Ошибка получения raw samples для {test_id}: {exc}")

        filtered_raw_samples = self._filter_metric_samples(metric_samples, db_key)
        latency_values = self._extract_latency_values(filtered_raw_samples)
        throughput_values = self._extract_throughput_values(filtered_raw_samples)

        aggregate_metrics = self._find_result_metrics(test_data, db_key)
        db_type = self._resolve_db_type(test_data, db_key, aggregate_metrics)
        latency_source = "metric_samples" if latency_values else None
        throughput_source = "metric_samples" if throughput_values else None

        if not latency_values or not throughput_values:
            series_points = await self._load_time_series(test_id, db_type)
            if not latency_values:
                latency_values = [
                    point.get("response_time")
                    for point in series_points
                    if point.get("response_time") is not None
                ]
                if latency_values:
                    latency_source = "time_series"
            if not throughput_values:
                throughput_values = [
                    point.get("throughput")
                    for point in series_points
                    if point.get("throughput") is not None
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
                latency_source,
                throughput_source,
                filtered_raw_samples,
                latency_values,
                throughput_values,
            ),
        }

    def _filter_metric_samples(self, metric_samples: List[Dict[str, Any]], db_key: str) -> List[Dict[str, Any]]:
        """Отфильтровать raw samples по ключу БД"""
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
        """Извлечь latency samples только из request_latency записей"""
        latency_values = []

        for point in metric_samples:
            if point.get("sample_type") != "request_latency":
                continue
            if point.get("latency_ms") is None:
                continue
            latency_values.append(point.get("latency_ms"))

        return latency_values

    def _extract_throughput_values(self, metric_samples: List[Dict[str, Any]]) -> List[float]:
        """Извлечь throughput samples из throughput_window записей"""
        throughput_values = []

        for point in metric_samples:
            if point.get("sample_type") != "throughput_window":
                continue

            value = point.get("throughput")
            if value is None:
                value = point.get("tps")
            if value is None:
                continue

            throughput_values.append(value)

        return throughput_values

    async def _load_time_series(self, test_id: str, db_type: str) -> List[Dict[str, Any]]:
        """Загрузить временной ряд для теста"""
        try:
            points = await self.repository.get_time_series(test_id, db_type=db_type, limit=5000)
        except Exception as exc:
            print(f"[COMPARISON] Ошибка получения time_series для {test_id}: {exc}")
            return []

        return [
            {
                "timestamp": point.get("timestamp"),
                "throughput": point.get("throughput"),
                "tps": point.get("tps"),
                "response_time": point.get("response_time"),
                "error_count": point.get("error_count"),
            }
            for point in points
        ]

    def _extract_db_type_from_key(self, db_key: str) -> str:
        """Определить db_type по ключу результата"""
        lower_key = db_key.lower()
        if "post" in lower_key:
            return "postgresql"
        if "maria" in lower_key:
            return "mariadb"
        if "mysql" in lower_key:
            return "mysql"
        return db_key

    def _resolve_db_type(self, test_data: Dict[str, Any], db_key: str, metrics: Dict[str, Any]) -> str:
        """Определить db_type для результата теста"""
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

        return self._extract_db_type_from_key(db_key)

    def _find_result_metrics(self, test_data: Dict[str, Any], db_key: str) -> Dict[str, Any]:
        """Найти агрегированные метрики для конкретной СУБД"""
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
        """Определить источник данных для статистики"""
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
        warnings: List[str],
        test_name: str,
        db_key: str,
    ) -> MetricStatsBundle:
        """Собрать bundle со статистикой по метрикам"""
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
            warnings.append(
                f"Для {test_name}/{db_key} отсутствуют raw latency samples; использованы агрегированные метрики"
            )

        if throughput_values:
            throughput_stats = calculate_descriptive_stats(throughput_values)
        elif aggregate_metrics:
            throughput_stats = self._build_stats_from_aggregates(aggregate_metrics, "throughput")
            warnings.append(
                f"Для {test_name}/{db_key} отсутствуют throughput samples; использованы агрегированные метрики"
            )

        if sample_size_warning:
            warnings.append(sample_size_warning)

        return MetricStatsBundle(
            latency_ms=latency_stats,
            throughput=throughput_stats,
            error_rate=self._resolve_error_rate(aggregate_metrics),
            total_duration_sec=self._resolve_total_duration(aggregate_metrics),
            source=samples_info["source"],
            sample_size_warning=sample_size_warning,
        )

    def _build_stats_from_aggregates(self, metrics: Dict[str, Any], metric_kind: str):
        """Построить псевдостатистику из агрегатов, если raw данных нет"""
        if metric_kind == "latency":
            avg_value = float(metrics.get("avg_time_ms", 0) or 0)
            min_value = float(metrics.get("min_time_ms", avg_value) or avg_value)
            max_value = float(metrics.get("max_time_ms", avg_value) or avg_value)
            p50_value = float(metrics.get("p50_time_ms", avg_value) or avg_value)
            p95_value = float(metrics.get("p95_time_ms", avg_value) or avg_value)
            p99_value = float(metrics.get("p99_time_ms", avg_value) or avg_value)
        else:
            avg_value = float(metrics.get("throughput", metrics.get("tps", 0)) or 0)
            min_value = avg_value
            max_value = avg_value
            p50_value = avg_value
            p95_value = avg_value
            p99_value = avg_value

        return calculate_descriptive_stats([min_value, p50_value, avg_value, p95_value, p99_value, max_value])

    def _resolve_error_rate(self, metrics: Dict[str, Any]) -> Optional[float]:
        """Извлечь error rate из агрегированных метрик"""
        if not metrics:
            return None
        value = metrics.get("error_rate")
        if value is None:
            return None
        return float(value)

    def _resolve_total_duration(self, metrics: Dict[str, Any]) -> Optional[float]:
        """Извлечь длительность выполнения"""
        if not metrics:
            return None
        if metrics.get("total_time_ms") is not None:
            return float(metrics["total_time_ms"]) / 1000.0
        return None

    def _build_normalized_metrics_map(
        self,
        tests: List[Dict[str, Any]],
        baseline_id: UUID,
        comparison_type: ComparisonType,
        descriptive_stats: Dict[str, Dict[str, MetricStatsBundle]],
        warnings: List[str],
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Построить нормализованные метрики для mixed/scalability сценариев"""
        if comparison_type not in (ComparisonType.SCALABILITY, ComparisonType.MIXED):
            return {}

        normalized_metrics: Dict[str, Dict[str, Dict[str, Any]]] = {}
        baseline_test = next((test for test in tests if UUID(str(test["id"])) == baseline_id), None)

        if baseline_test is None:
            raise ValueError("Baseline-тест не найден среди загруженных данных")

        baseline_key = str(baseline_id)
        baseline_descriptive = descriptive_stats.get(baseline_key, {})

        for test_data in tests:
            test_key = str(test_data["id"])
            normalized_metrics[test_key] = {}

            for db_key, metrics_bundle in descriptive_stats.get(test_key, {}).items():
                baseline_bundle = baseline_descriptive.get(db_key)
                normalized = self._normalize_metrics(
                    test_data=test_data,
                    db_key=db_key,
                    metrics_bundle=metrics_bundle,
                    baseline_test=baseline_test,
                    baseline_bundle=baseline_bundle,
                    comparison_type=comparison_type,
                )
                normalized_metrics[test_key][db_key] = asdict(normalized)

                if normalized.normalization_warning:
                    warnings.append(
                        f"{test_data.get('name')}/{db_key}: {normalized.normalization_warning}"
                    )

        return normalized_metrics

    def _normalize_metrics(
        self,
        test_data: Dict[str, Any],
        db_key: str,
        metrics_bundle: MetricStatsBundle,
        baseline_test: Dict[str, Any],
        baseline_bundle: Optional[MetricStatsBundle],
        comparison_type: ComparisonType,
    ) -> NormalizedMetrics:
        """Нормализовать метрики теста для сравнения разных конфигураций"""
        threads = self._resolve_thread_count(test_data)
        duration_seconds = self._resolve_test_duration_seconds(test_data, metrics_bundle)
        throughput_abs = metrics_bundle.throughput.mean if metrics_bundle.throughput else None
        latency_mean_abs = metrics_bundle.latency_ms.mean if metrics_bundle.latency_ms else None
        throughput_per_thread = None
        throughput_per_second = None
        scaling_efficiency = None
        latency_per_thread = None
        normalization_warning = None

        if threads <= 0:
            normalization_warning = "Не удалось вычислить нормализацию: число потоков равно 0"
        else:
            if throughput_abs is not None:
                throughput_per_thread = throughput_abs / float(threads)
            if latency_mean_abs is not None:
                latency_per_thread = latency_mean_abs / float(threads)

        total_transactions = self._resolve_total_transactions(test_data, db_key)
        if total_transactions is not None and duration_seconds and duration_seconds > 0:
            throughput_per_second = total_transactions / duration_seconds
        elif throughput_abs is not None:
            throughput_per_second = throughput_abs

        if comparison_type in (ComparisonType.SCALABILITY, ComparisonType.MIXED):
            baseline_threads = self._resolve_thread_count(baseline_test)
            baseline_throughput = baseline_bundle.throughput.mean if baseline_bundle and baseline_bundle.throughput else None
            if baseline_threads <= 0 or baseline_throughput is None or throughput_abs is None:
                if normalization_warning is None:
                    normalization_warning = (
                        "Недостаточно baseline-данных для расчёта scaling efficiency"
                    )
            else:
                expected_throughput = baseline_throughput * (float(threads) / float(baseline_threads))
                if expected_throughput > 0:
                    scaling_efficiency = throughput_abs / expected_throughput
                else:
                    normalization_warning = (
                        "Не удалось вычислить scaling efficiency: ожидаемый throughput равен 0"
                    )

        source_metrics = [
            metric_name
            for metric_name, metric_value in (
                ("throughput_abs", throughput_abs),
                ("latency_mean_abs", latency_mean_abs),
                ("throughput_per_thread", throughput_per_thread),
                ("throughput_per_second", throughput_per_second),
                ("scaling_efficiency", scaling_efficiency),
                ("latency_per_thread", latency_per_thread),
            )
            if metric_value is not None
        ]

        return NormalizedMetrics(
            throughput_abs=throughput_abs,
            latency_mean_abs=latency_mean_abs,
            throughput_per_thread=throughput_per_thread,
            throughput_per_second=throughput_per_second,
            scaling_efficiency=scaling_efficiency,
            latency_per_thread=latency_per_thread,
            threads=threads if threads > 0 else None,
            duration_seconds=duration_seconds,
            source_metrics=source_metrics,
            normalization_warning=normalization_warning,
        )

    def _resolve_thread_count(self, test_data: Dict[str, Any]) -> int:
        """Получить число потоков/виртуальных пользователей для теста"""
        config = test_data.get("config", {}) or {}

        for field_name in ("virtual_users", "threads", "num_threads"):
            value = config.get(field_name)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue

        return 0

    def _resolve_test_duration_seconds(
        self,
        test_data: Dict[str, Any],
        metrics_bundle: MetricStatsBundle,
    ) -> Optional[float]:
        """Определить фактическую длительность теста в секундах"""
        if metrics_bundle.total_duration_sec is not None:
            return metrics_bundle.total_duration_sec

        summary = test_data.get("summary", {}) or {}
        if summary.get("total_duration") is not None:
            try:
                return float(summary["total_duration"])
            except (TypeError, ValueError):
                return None

        config = test_data.get("config", {}) or {}
        if config.get("duration") is not None:
            try:
                return float(config["duration"])
            except (TypeError, ValueError):
                return None

        return None

    def _resolve_total_transactions(self, test_data: Dict[str, Any], db_key: str) -> Optional[float]:
        """Определить общее число транзакций/запросов для теста"""
        metrics = self._find_result_metrics(test_data, db_key)
        successful = metrics.get("successful")
        failed = metrics.get("failed")

        if successful is not None or failed is not None:
            try:
                return float(successful or 0) + float(failed or 0)
            except (TypeError, ValueError):
                return None

        summary = test_data.get("summary", {}) or {}
        total_transactions = summary.get("total_transactions")
        if total_transactions is None:
            return None

        try:
            return float(total_transactions)
        except (TypeError, ValueError):
            return None

    def _build_pairwise_comparisons(
        self,
        tests: List[Dict[str, Any]],
        baseline_id: UUID,
        comparison_type: ComparisonType,
        raw_samples: Dict[str, Dict[str, Dict[str, Any]]],
        normalized_metrics: Dict[str, Dict[str, Dict[str, Any]]],
        warnings: List[str],
    ) -> List:
        """Построить попарные сравнения относительно baseline"""
        comparisons = []
        baseline_key = str(baseline_id)
        baseline_test = None

        for test_data in tests:
            if str(test_data["id"]) == baseline_key:
                baseline_test = test_data
                break

        if not baseline_test:
            raise ValueError("Baseline-тест не найден среди загруженных данных")

        baseline_db_keys = self._get_test_db_keys(baseline_test)

        for test_data in tests:
            compared_id = UUID(str(test_data["id"]))
            if compared_id == baseline_id:
                continue

            db_pairs = self._resolve_db_pairs_for_comparison(
                baseline_test=baseline_test,
                compared_test=test_data,
                comparison_type=comparison_type,
                warnings=warnings,
            )

            for baseline_db_key, compared_db_key, display_db_key in db_pairs:
                baseline_info = raw_samples.get(baseline_key, {}).get(baseline_db_key, {})
                compared_info = raw_samples.get(str(compared_id), {}).get(compared_db_key, {})

                if not baseline_info:
                    warnings.append(f"Baseline-тест не содержит данных для {baseline_db_key}")
                    continue

                if not compared_info:
                    warnings.append(f"Тест {test_data.get('name')} не содержит данных для {compared_db_key}")
                    continue

                comparisons.append(
                    compare_two_samples(
                        a=baseline_info.get("latency_values", []),
                        b=compared_info.get("latency_values", []),
                        baseline_test_id=baseline_id,
                        compared_test_id=compared_id,
                        db_key=display_db_key,
                        metric="latency_ms",
                    )
                )

                comparisons.append(
                    compare_two_samples(
                        a=baseline_info.get("throughput_values", []),
                        b=compared_info.get("throughput_values", []),
                        baseline_test_id=baseline_id,
                        compared_test_id=compared_id,
                        db_key=display_db_key,
                        metric="throughput",
                    )
                )

                if comparison_type in (ComparisonType.SCALABILITY, ComparisonType.MIXED):
                    baseline_threads = self._resolve_thread_count(baseline_test)
                    compared_threads = self._resolve_thread_count(test_data)
                    if baseline_threads > 0 and compared_threads > 0:
                        baseline_normalized_samples = [
                            value / float(baseline_threads)
                            for value in baseline_info.get("throughput_values", [])
                        ]
                        compared_normalized_samples = [
                            value / float(compared_threads)
                            for value in compared_info.get("throughput_values", [])
                        ]
                        comparisons.append(
                            compare_two_samples(
                                a=baseline_normalized_samples,
                                b=compared_normalized_samples,
                                baseline_test_id=baseline_id,
                                compared_test_id=compared_id,
                                db_key=display_db_key,
                                metric="throughput_per_thread",
                            )
                        )

                    baseline_efficiency = (
                        normalized_metrics.get(baseline_key, {})
                        .get(baseline_db_key, {})
                        .get("scaling_efficiency")
                    )
                    compared_efficiency = (
                        normalized_metrics.get(str(compared_id), {})
                        .get(compared_db_key, {})
                        .get("scaling_efficiency")
                    )
                    if baseline_efficiency is not None and compared_efficiency is not None:
                        pct_difference = None
                        if baseline_efficiency != 0:
                            pct_difference = (
                                (compared_efficiency - baseline_efficiency) / baseline_efficiency
                            ) * 100.0
                        comparisons.append(
                            {
                                "baseline_test_id": baseline_id,
                                "compared_test_id": compared_id,
                                "db_key": display_db_key,
                                "metric": "scaling_efficiency",
                                "baseline_mean": baseline_efficiency,
                                "compared_mean": compared_efficiency,
                                "pct_difference": pct_difference,
                                "test_used": None,
                                "statistic": None,
                                "p_value": None,
                                "is_significant": False,
                                "interpretation": "Сравнение scaling efficiency выполнено без статистического теста",
                                "warning": "Scaling efficiency рассчитывается как нормализованная производная метрика",
                            }
                        )

        return comparisons

    def _resolve_db_pairs_for_comparison(
        self,
        baseline_test: Dict[str, Any],
        compared_test: Dict[str, Any],
        comparison_type: ComparisonType,
        warnings: List[str],
    ) -> List:
        """Определить пары db_key для попарного сравнения"""
        baseline_db_keys = self._get_test_db_keys(baseline_test)
        compared_db_keys = self._get_test_db_keys(compared_test)

        if comparison_type == ComparisonType.CROSS_DATABASE:
            if len(baseline_db_keys) == 1 and len(compared_db_keys) == 1:
                return [
                    (
                        baseline_db_keys[0],
                        compared_db_keys[0],
                        f"{baseline_db_keys[0]} vs {compared_db_keys[0]}",
                    )
                ]

            zipped_pairs = list(zip(baseline_db_keys, compared_db_keys))
            if zipped_pairs:
                warnings.append(
                    "Для cross-database сравнения с несколькими целевыми БД пары сопоставлены по позиции в списке результатов"
                )
                return [
                    (baseline_db_key, compared_db_key, f"{baseline_db_key} vs {compared_db_key}")
                    for baseline_db_key, compared_db_key in zipped_pairs
                ]

            return []

        common_db_keys = [db_key for db_key in baseline_db_keys if db_key in compared_db_keys]
        return [(db_key, db_key, db_key) for db_key in common_db_keys]

    async def _build_test_info(self, test_data: Dict[str, Any]) -> ComparisonTestInfo:
        """Преобразовать словарь теста в схему ответа с развёрнутой информацией"""
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
        )

    async def _resolve_scenario_info(self, config: Dict[str, Any]) -> Optional[ScenarioInfo]:
        """Разрешить сценарий из snapshot config или активного bundle."""
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
                sql_template=query.get("sql_template", ""),
                query_type=query.get("query_type", "unknown"),
                weight=query.get("weight", 1),
                description=query.get("description"),
            )
            for query in snapshot.get("queries", []) or []
        ]
        return ScenarioInfo(
            name=snapshot.get("name", "Без названия"),
            description=snapshot.get("description"),
            scenario_type=snapshot.get("scenario_template_id") or snapshot.get("scenario_type", "unknown"),
            queries=queries,
        )

    async def _resolve_connections(self, connection_ids: Optional[List[str]]) -> List[ConnectionInfo]:
        """Разрешить имена подключений по ID"""
        if not connection_ids or not self.connection_repository:
            return []

        connections = []
        for conn_id in connection_ids:
            try:
                conn = await self.connection_repository.get_connection_by_id(conn_id)
                if conn:
                    connections.append(ConnectionInfo(
                        id=str(conn.id),
                        name=conn.name,
                        dbms_type=conn.dbms_type,
                        host=conn.host,
                        port=conn.port,
                        database=conn.database,
                    ))
            except Exception as exc:
                print(f"[COMPARISON] Не удалось разрешить подключение '{conn_id}': {exc}")

        return connections

    @staticmethod
    def _replace_db_keys_in_report(report, db_key_labels: Dict[str, str]):
        """Заменить UUID db_key в тексте отчёта на человекочитаемые метки"""
        def _replace_text(text: str) -> str:
            for uuid_key, label in db_key_labels.items():
                text = text.replace(uuid_key, label)
            return text

        report.verdict = _replace_text(report.verdict)
        report.patterns = [_replace_text(item) for item in report.patterns]
        report.recommendations = [_replace_text(item) for item in report.recommendations]
        report.hypotheses = [_replace_text(item) for item in report.hypotheses]
        for section in report.sections:
            section.title = _replace_text(section.title)
            section.items = [_replace_text(item) for item in section.items]

    def _build_db_key_labels(self, tests: List[Dict[str, Any]]) -> Dict[str, str]:
        """Построить маппинг db_key -> человекочитаемое имя из результатов тестов"""
        labels: Dict[str, str] = {}

        for test_data in tests:
            for result in test_data.get("results", []) or []:
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

    def _deduplicate_warnings(self, warnings: List[str]) -> List[str]:
        """Удалить дубли предупреждений, сохранив порядок"""
        unique_warnings = []
        seen = set()

        for warning in warnings:
            if warning in seen:
                continue
            unique_warnings.append(warning)
            seen.add(warning)

        return unique_warnings
