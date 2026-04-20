"""
Pydantic схемы для сравнительного анализа тестов
"""
from dataclasses import field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass


class ComparisonType(str, Enum):
    """Тип сравнительного анализа (derived label from traits)"""

    CROSS_DATABASE = "cross_database"
    SCALABILITY = "scalability"
    CONFIG_COMPARISON = "config_comparison"
    TEMPORAL = "temporal"
    GENERAL = "general"

    # Keep MIXED as an alias so old serialized data still deserialises
    MIXED = "mixed"


@dataclass
class ComparisonTraits:
    """Boolean dimensions describing the comparison rather than a rigid type."""

    same_scenario: bool = True
    same_db_targets: bool = True
    multiple_dbs: bool = False
    same_load_params: bool = True
    diff_virtual_users: bool = False
    diff_iterations: bool = False
    diff_warmup: bool = False
    is_temporal: bool = False


class ComparisonRequest(BaseModel):
    """Запрос на сравнительный анализ тестов"""

    test_ids: List[UUID] = Field(..., min_length=2, max_length=5, description="ID тестов для сравнения")
    baseline_id: Optional[UUID] = Field(default=None, description="ID baseline-теста")
    report_config: Optional["AnalysisReportConfig"] = None


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
    queries: List[ScenarioQueryInfo] = Field(default_factory=list)


class ConnectionInfo(BaseModel):
    """Информация о подключении к СУБД"""

    id: str
    name: str
    dbms_type: str
    host: str
    port: int
    database: str


class ComparisonTestInfo(BaseModel):
    """Краткая информация о тесте для ответа"""

    id: UUID
    name: str
    status: str
    config: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    scenario_info: Optional[ScenarioInfo] = None
    connections: List[ConnectionInfo] = Field(default_factory=list)
    logical_database_id: Optional[str] = None
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
    """Набор метрик для одного теста и одной СУБД"""

    latency_ms: Optional[DescriptiveStats] = None
    throughput: Optional[DescriptiveStats] = None
    error_rate: Optional[float] = None
    total_duration_sec: Optional[float] = None
    source: str = "unknown"
    sample_size_warning: Optional[str] = None


@dataclass
class NormalizedMetrics:
    """Нормализованные метрики для сравнения разных конфигураций"""

    throughput_abs: Optional[float] = None
    latency_mean_abs: Optional[float] = None
    throughput_per_thread: Optional[float] = None
    throughput_per_second: Optional[float] = None
    scaling_efficiency: Optional[float] = None
    latency_per_thread: Optional[float] = None
    threads: Optional[int] = None
    duration_seconds: Optional[float] = None
    source_metrics: List[str] = field(default_factory=list)
    normalization_warning: Optional[str] = None


class PairwiseComparison(BaseModel):
    """Результат попарного сравнения тестов"""

    baseline_test_id: UUID
    compared_test_id: UUID
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


class BarChartPoint(BaseModel):
    """Точка данных для bar chart"""

    test_id: UUID
    test_name: str
    db_key: str
    latency_mean: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    throughput_mean: Optional[float] = None
    error_rate: Optional[float] = None


class BoxPlotPoint(BaseModel):
    """Точка данных для box plot"""

    test_id: UUID
    test_name: str
    db_key: str
    min: float
    q1: float
    median: float
    q3: float
    max: float
    sample_count: int


class ThroughputSeriesPoint(BaseModel):
    """Точка временного ряда throughput"""

    timestamp: Optional[str] = None
    throughput: Optional[float] = None
    tps: Optional[float] = None
    response_time: Optional[float] = None
    error_count: Optional[int] = None


class ComparisonChartsData(BaseModel):
    """Данные для сравнительных графиков"""

    bar_chart: List[BarChartPoint] = Field(default_factory=list)
    box_plot: List[BoxPlotPoint] = Field(default_factory=list)
    throughput_series: Dict[str, List[ThroughputSeriesPoint]] = Field(default_factory=dict)


class AnalysisSection(BaseModel):
    """Секция аналитического отчёта"""

    title: str
    items: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """Rule-based аналитический отчёт по сравнению тестов"""

    verdict: str
    patterns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    sections: List[AnalysisSection] = Field(default_factory=list)


class AnalysisReportConfig(BaseModel):
    """Конфигурация включения уровней аналитического отчёта"""

    include_verdict: bool = True
    include_patterns: bool = True
    include_recommendations: bool = True
    include_hypotheses: bool = True


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
    """Сводка влияния параметров для одного теста относительно baseline"""

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
    lock_waits: Optional[int] = None
    deadlocks: Optional[int] = None


class ComparisonResult(BaseModel):
    """Полный результат сравнительного анализа"""

    tests: List[ComparisonTestInfo]
    baseline_id: UUID
    comparison_type: ComparisonType
    traits: Optional[ComparisonTraits] = None
    warnings: List[str] = Field(default_factory=list)
    descriptive_stats: Dict[str, Dict[str, MetricStatsBundle]] = Field(default_factory=dict)
    normalized_metrics: Dict[str, Dict[str, NormalizedMetrics]] = Field(default_factory=dict)
    pairwise_comparisons: List[PairwiseComparison] = Field(default_factory=list)
    charts_data: ComparisonChartsData = Field(default_factory=ComparisonChartsData)
    analysis_report: Optional[AnalysisReport] = None
    db_key_labels: Dict[str, str] = Field(default_factory=dict, description="Маппинг db_key (UUID) -> человекочитаемое имя")
    parameter_impacts: List[ParameterImpactSummary] = Field(default_factory=list)
    resource_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


ComparisonRequest.model_rebuild()
