"""
Pydantic схемы для двухрежимного сравнительного анализа прогонов.

Два режима анализа:
- per_test: внутритестовый (один прогон, сравнение СУБД на одной нагрузке)
- series: серийный по СУБД (несколько прогонов, анализ траекторий при разных нагрузках)
"""
from dataclasses import field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from pydantic.dataclasses import dataclass


# ---------------------------------------------------------------------------
# Режим анализа
# ---------------------------------------------------------------------------

class AnalysisMode(str, Enum):
    PER_TEST = "per_test"
    SERIES = "series"


# ---------------------------------------------------------------------------
# Предупреждения
# ---------------------------------------------------------------------------

class AnalysisWarning(BaseModel):
    """Типизированное предупреждение анализа"""

    severity: Literal["info", "warn", "block"]
    code: str
    message: str


# ---------------------------------------------------------------------------
# Сравнимость серии
# ---------------------------------------------------------------------------

class ComparabilityReport(BaseModel):
    """Отчёт о сопоставимости прогонов для серийного анализа"""

    same_scenario: bool = True
    same_workload_mode: bool = True
    same_query_ids: bool = True
    same_transaction_ids: bool = True
    same_schema_profile: bool = True
    same_load_params: bool = True
    is_valid_for_series: bool = True
    reasons: List[str] = Field(default_factory=list)


class LoadLevel(BaseModel):
    """Один уровень нагрузки в серии"""

    level_id: str
    virtual_users: int
    iterations: int
    warmup_time: float = 0.0
    label: str = ""
    test_ids: List[UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Запрос на анализ
# ---------------------------------------------------------------------------

class AnalysisReportConfig(BaseModel):
    """Конфигурация включения уровней аналитического отчёта"""

    include_verdict: bool = True
    include_patterns: bool = True
    include_recommendations: bool = True
    include_hypotheses: bool = True


class ComparisonRequest(BaseModel):
    """Запрос на сравнительный анализ прогонов"""

    analysis_mode: AnalysisMode
    test_ids: List[UUID] = Field(..., min_length=1, max_length=5)
    baseline_id: Optional[UUID] = Field(default=None, description="ID baseline-прогона (для серии)")
    report_config: Optional[AnalysisReportConfig] = None

    @model_validator(mode="after")
    def _validate_mode_constraints(self):
        if self.analysis_mode == AnalysisMode.PER_TEST and len(self.test_ids) != 1:
            raise ValueError("Режим per_test требует ровно один test_id")
        if self.analysis_mode == AnalysisMode.SERIES and len(self.test_ids) < 2:
            raise ValueError("Режим series требует минимум 2 test_id")
        return self


# ---------------------------------------------------------------------------
# Общие модели (переиспользуются обоими режимами)
# ---------------------------------------------------------------------------

class ScenarioTransactionStepInfo(BaseModel):
    """Шаг SQL внутри транзакции сценария"""

    sql_template: str
    query_type: str
    order_index: int = 0
    description: Optional[str] = None


class ScenarioTransactionInfo(BaseModel):
    """Транзакция в transaction bundle"""

    name: str
    weight: int = 1
    description: Optional[str] = None
    steps: List[ScenarioTransactionStepInfo] = Field(default_factory=list)


class ScenarioQueryInfo(BaseModel):
    """Информация о SQL-запросе сценария"""

    sql_template: str
    query_type: str
    weight: int = 1
    description: Optional[str] = None


class ScenarioInfo(BaseModel):
    """Развёрнутая информация о сценарии тестирования"""

    name: str
    description: Optional[str] = None
    scenario_type: str
    workload_mode: str = "query"
    primary_rate_unit: str = "qps"
    queries: List[ScenarioQueryInfo] = Field(default_factory=list)
    transactions: List[ScenarioTransactionInfo] = Field(default_factory=list)


class ConnectionInfo(BaseModel):
    """Информация о подключении к СУБД"""

    id: str
    name: str
    dbms_type: str
    host: str
    port: int
    database: str


class ComparisonTestInfo(BaseModel):
    """Краткая информация о прогоне для ответа"""

    id: UUID
    name: str
    status: str
    config: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    scenario_info: Optional[ScenarioInfo] = None
    connections: List[ConnectionInfo] = Field(default_factory=list)
    database_group_id: Optional[str] = None
    use_indexes: Optional[bool] = None


class DescriptiveStats(BaseModel):
    """Описательная статистика по числовой выборке"""

    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    cv: float = 0.0
    iqr: float = 0.0


class MetricStatsBundle(BaseModel):
    """Набор метрик для одного прогона и одной СУБД"""

    latency_ms: Optional[DescriptiveStats] = None
    throughput: Optional[DescriptiveStats] = None
    error_rate: Optional[float] = None
    total_duration_sec: Optional[float] = None
    source: str = "unknown"
    sample_size_warning: Optional[str] = None


class PairwiseComparison(BaseModel):
    """Результат попарного сравнения двух выборок"""

    baseline_id: str
    compared_id: str
    db_key: str
    metric: str
    baseline_mean: Optional[float] = None
    compared_mean: Optional[float] = None
    pct_difference: Optional[float] = None
    test_used: Optional[str] = None
    statistic: Optional[float] = None
    p_value: Optional[float] = None
    is_significant: bool = False
    interpretation: str
    warning: Optional[str] = None
    effect_size: Optional[float] = None
    effect_size_label: Optional[str] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    p_value_adjusted: Optional[float] = None
    is_significant_adjusted: bool = False


# ---------------------------------------------------------------------------
# Графики — общие точки
# ---------------------------------------------------------------------------

class BarChartPoint(BaseModel):
    """Точка данных для bar chart"""

    label: str
    db_key: str
    latency_mean: Optional[float] = None
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    throughput_mean: Optional[float] = None
    error_rate: Optional[float] = None


class BoxPlotPoint(BaseModel):
    """Точка данных для box plot"""

    label: str
    db_key: str
    min: float
    q1: float
    median: float
    q3: float
    max: float
    sample_count: int


class ThroughputSeriesPoint(BaseModel):
    """Точка временного ряда пропускной способности"""

    timestamp: Optional[str] = None
    throughput: Optional[float] = None
    attempt_rate: Optional[float] = None
    response_time: Optional[float] = None
    error_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Аналитический отчёт
# ---------------------------------------------------------------------------

class AnalysisSection(BaseModel):
    """Секция аналитического отчёта"""

    title: str
    items: List[str] = Field(default_factory=list)


class DbFindingStatus(str, Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


class DbMetricChip(BaseModel):
    """Компактный числовой показатель для scorecard СУБД"""

    label: str
    value: str
    tone: Literal["neutral", "positive", "negative"] = "neutral"


class DbFinding(BaseModel):
    """Scorecard одной СУБД: статус, числовые chips и краткие выводы"""

    db_key: str
    db_label: str
    status: DbFindingStatus
    status_reason: str
    chips: List[DbMetricChip] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """Rule-based аналитический отчёт"""

    verdict: str
    patterns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    sections: List[AnalysisSection] = Field(default_factory=list)
    per_db_findings: List[DbFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parameter impact
# ---------------------------------------------------------------------------

class ChangedParameter(BaseModel):
    """Один изменившийся параметр конфигурации"""

    parameter: str
    label: str
    baseline_value: Optional[Any] = None
    compared_value: Optional[Any] = None
    change_description: str


class MetricEffect(BaseModel):
    """Влияние на одну метрику для одной СУБД"""

    db_key: str
    db_label: Optional[str] = None
    metric: Literal["throughput", "latency_mean", "latency_p99", "latency_cv"]
    baseline_value: float
    compared_value: float
    pct_change: float
    direction: Literal["up", "down", "flat"]
    is_improvement: bool
    magnitude: Literal["negligible", "small", "medium", "large"]


class ParameterImpactSummary(BaseModel):
    """Сводка влияния параметров для одного прогона относительно baseline"""

    test_id: UUID
    test_name: str
    vs_baseline: str
    changed_parameters: List[ChangedParameter] = Field(default_factory=list)
    metric_effects: List[MetricEffect] = Field(default_factory=list)
    top_insights: List[str] = Field(default_factory=list)
    summary_text: str = ""


@dataclass
class ResourceMetrics:
    """System and DBMS resource metrics snapshot for one test + db_key."""

    cpu_usage: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    disk_iops: Optional[float] = None
    cache_hit_ratio: Optional[float] = None
    buffer_pool_hit_ratio: Optional[float] = None
    cache_hit_ratio_status: Optional[str] = None
    cache_hit_ratio_note: Optional[str] = None
    cache_hit_ratio_mode: Optional[str] = None
    lock_waits: Optional[int] = None
    deadlocks: Optional[int] = None


# ---------------------------------------------------------------------------
# Режим A: Per-test (внутритестовый анализ)
# ---------------------------------------------------------------------------

class DbRankEntry(BaseModel):
    """Позиция одной СУБД в ранжировании по метрике"""

    db_key: str
    db_label: Optional[str] = None
    rank: int
    value: float


class MetricRanking(BaseModel):
    """Ранжирование СУБД по одной метрике"""

    metric: str
    rankings: List[DbRankEntry] = Field(default_factory=list)
    best_db_key: str


class PerTestCharts(BaseModel):
    """Графики для внутритестового режима"""

    bar_chart: List[BarChartPoint] = Field(default_factory=list)
    box_plot: List[BoxPlotPoint] = Field(default_factory=list)
    throughput_series: Dict[str, List[ThroughputSeriesPoint]] = Field(default_factory=dict)


class PerTestResult(BaseModel):
    """Результат внутритестового анализа (один прогон, сравнение СУБД)"""

    analysis_mode: Literal["per_test"] = "per_test"
    test: ComparisonTestInfo
    warnings: List[AnalysisWarning] = Field(default_factory=list)
    descriptive_stats: Dict[str, MetricStatsBundle] = Field(default_factory=dict)
    pairwise: List[PairwiseComparison] = Field(default_factory=list)
    rankings: List[MetricRanking] = Field(default_factory=list)
    charts: PerTestCharts = Field(default_factory=PerTestCharts)
    analysis_report: Optional[AnalysisReport] = None
    db_key_labels: Dict[str, str] = Field(default_factory=dict)
    resource_metrics: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Режим B: Series (серийный анализ по СУБД)
# ---------------------------------------------------------------------------

class TrajectoryPoint(BaseModel):
    """Одна точка траектории СУБД при определённом уровне нагрузки"""

    level_id: str
    load_label: str
    throughput_mean: Optional[float] = None
    latency_mean: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    error_rate: Optional[float] = None
    cv: Optional[float] = None


class TrendTestResult(BaseModel):
    """Результат одного тренд-теста"""

    statistic: float
    p_value: float
    direction: Literal["increasing", "decreasing", "no_trend"]


class DegradationIndex(BaseModel):
    """Индекс деградации p95/p99 по уровням нагрузки"""

    p95_changes: List[float] = Field(default_factory=list)
    p99_changes: List[float] = Field(default_factory=list)
    overall_p95: float = 0.0
    overall_p99: float = 0.0


class DbSeriesSummary(BaseModel):
    """Сводка серийного анализа для одной СУБД"""

    db_key: str
    db_label: Optional[str] = None
    trajectory: List[TrajectoryPoint] = Field(default_factory=list)
    degradation: DegradationIndex = Field(default_factory=DegradationIndex)
    stability_index: Optional[float] = None
    elasticity: Optional[float] = None
    saturation_point: Optional[str] = None
    trend_tests: Dict[str, TrendTestResult] = Field(default_factory=dict)
    adjacent_level_tests: List[PairwiseComparison] = Field(default_factory=list)
    descriptive_stats_by_level: Dict[str, MetricStatsBundle] = Field(default_factory=dict)


class CrossDbLevelRank(BaseModel):
    """Кросс-СУБД ранжирование на одном уровне нагрузки"""

    level_id: str
    load_label: str
    metric: str
    rankings: List[DbRankEntry] = Field(default_factory=list)


class SeriesChartPoint(BaseModel):
    """Точка графика серии (СУБД × уровень нагрузки)"""

    level_id: str
    load_label: str
    value: Optional[float] = None


class SeriesCharts(BaseModel):
    """Графики для серийного режима"""

    throughput_by_load: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    latency_by_load: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    p95_by_load: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    p99_by_load: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    error_rate_by_load: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    scaling_efficiency: Dict[str, List[SeriesChartPoint]] = Field(default_factory=dict)
    bar_chart: List[BarChartPoint] = Field(default_factory=list)
    box_plot: List[BoxPlotPoint] = Field(default_factory=list)


class SeriesResult(BaseModel):
    """Результат серийного анализа по СУБД (несколько прогонов, разные нагрузки)"""

    analysis_mode: Literal["series"] = "series"
    tests: List[ComparisonTestInfo]
    baseline_id: UUID
    comparability: ComparabilityReport
    load_levels: List[LoadLevel] = Field(default_factory=list)
    per_db: Dict[str, DbSeriesSummary] = Field(default_factory=dict)
    cross_db_ranks: List[CrossDbLevelRank] = Field(default_factory=list)
    charts: SeriesCharts = Field(default_factory=SeriesCharts)
    analysis_report: Optional[AnalysisReport] = None
    db_key_labels: Dict[str, str] = Field(default_factory=dict)
    parameter_impacts: List[ParameterImpactSummary] = Field(default_factory=list)
    warnings: List[AnalysisWarning] = Field(default_factory=list)
    resource_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Union-тип для ответа API
# ---------------------------------------------------------------------------

ComparisonResult = Union[PerTestResult, SeriesResult]
