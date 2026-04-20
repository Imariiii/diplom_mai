/**
 * API клиент — Двухрежимный анализ прогонов
 */
import { apiClient } from "./client"

// ---------------------------------------------------------------------------
// Режим анализа
// ---------------------------------------------------------------------------

export type AnalysisMode = "per_test" | "series"

// ---------------------------------------------------------------------------
// Запрос
// ---------------------------------------------------------------------------

export interface AnalysisReportConfig {
  include_verdict: boolean
  include_patterns: boolean
  include_recommendations: boolean
  include_hypotheses: boolean
}

export interface ComparisonRequest {
  analysis_mode: AnalysisMode
  test_ids: string[]
  baseline_id?: string
  report_config?: AnalysisReportConfig
}

// ---------------------------------------------------------------------------
// Предупреждения и сравнимость
// ---------------------------------------------------------------------------

export type WarningSeverity = "info" | "warn" | "block"

export interface AnalysisWarning {
  severity: WarningSeverity
  code: string
  message: string
}

export interface ComparabilityReport {
  same_scenario: boolean
  same_query_ids: boolean
  same_schema_profile: boolean
  same_load_params: boolean
  is_valid_for_series: boolean
  reasons: string[]
}

export interface LoadLevel {
  level_id: string
  virtual_users: number
  iterations: number
  warmup_time: number
  label: string
  test_ids: string[]
}

// ---------------------------------------------------------------------------
// Общие модели
// ---------------------------------------------------------------------------

export interface ScenarioQueryInfo {
  sql_template: string
  query_type: string
  weight: number
  description?: string | null
}

export interface ScenarioInfo {
  name: string
  description?: string | null
  scenario_type: string
  queries: ScenarioQueryInfo[]
}

export interface ConnectionInfo {
  id: string
  name: string
  dbms_type: string
  host: string
  port: number
  database: string
}

export interface ComparisonTestInfo {
  id: string
  name: string
  status: string
  config: Record<string, any>
  summary?: Record<string, any> | null
  started_at?: string | null
  finished_at?: string | null
  scenario_info?: ScenarioInfo | null
  connections: ConnectionInfo[]
  logical_database_id?: string | null
  use_indexes?: boolean | null
}

export interface DescriptiveStats {
  count: number
  mean: number
  median: number
  std: number
  min: number
  max: number
  p50: number
  p95: number
  p99: number
  cv: number
  iqr: number
}

export interface MetricStatsBundle {
  latency_ms?: DescriptiveStats | null
  throughput?: DescriptiveStats | null
  error_rate?: number | null
  total_duration_sec?: number | null
  source: string
  sample_size_warning?: string | null
}

export interface PairwiseComparison {
  baseline_id: string
  compared_id: string
  db_key: string
  metric: string
  baseline_mean?: number | null
  compared_mean?: number | null
  pct_difference?: number | null
  test_used?: string | null
  statistic?: number | null
  p_value?: number | null
  is_significant: boolean
  interpretation: string
  warning?: string | null
  effect_size?: number | null
  effect_size_label?: string | null
  ci_lower?: number | null
  ci_upper?: number | null
  p_value_adjusted?: number | null
  is_significant_adjusted: boolean
}

// ---------------------------------------------------------------------------
// Графики — общие точки
// ---------------------------------------------------------------------------

export interface BarChartPoint {
  label: string
  db_key: string
  latency_mean?: number | null
  latency_p95?: number | null
  latency_p99?: number | null
  throughput_mean?: number | null
  error_rate?: number | null
}

export interface BoxPlotPoint {
  label: string
  db_key: string
  min: number
  q1: number
  median: number
  q3: number
  max: number
  sample_count: number
}

export interface ThroughputSeriesPoint {
  timestamp?: string | null
  throughput?: number | null
  tps?: number | null
  response_time?: number | null
  error_count?: number | null
}

// ---------------------------------------------------------------------------
// Аналитический отчёт
// ---------------------------------------------------------------------------

export interface AnalysisSection {
  title: string
  items: string[]
}

export interface AnalysisReport {
  verdict: string
  patterns: string[]
  recommendations: string[]
  hypotheses: string[]
  sections: AnalysisSection[]
}

// ---------------------------------------------------------------------------
// Parameter impact
// ---------------------------------------------------------------------------

export interface ChangedParameter {
  parameter: string
  label: string
  baseline_value?: any
  compared_value?: any
  change_description: string
}

export type MetricEffectMetric = "throughput" | "latency_mean" | "latency_p99" | "latency_cv"
export type MetricEffectDirection = "up" | "down" | "flat"
export type MetricEffectMagnitude = "negligible" | "small" | "medium" | "large"

export interface MetricEffect {
  db_key: string
  db_label?: string | null
  metric: MetricEffectMetric
  baseline_value: number
  compared_value: number
  pct_change: number
  direction: MetricEffectDirection
  is_improvement: boolean
  magnitude: MetricEffectMagnitude
}

export interface ParameterImpactSummary {
  test_id: string
  test_name: string
  vs_baseline: string
  changed_parameters: ChangedParameter[]
  metric_effects: MetricEffect[]
  top_insights: string[]
  summary_text: string
}

export interface ResourceMetrics {
  cpu_usage?: number | null
  memory_usage_percent?: number | null
  disk_iops?: number | null
  cache_hit_ratio?: number | null
  buffer_pool_hit_ratio?: number | null
  lock_waits?: number | null
  deadlocks?: number | null
}

// ---------------------------------------------------------------------------
// Режим A: Per-test
// ---------------------------------------------------------------------------

export interface DbRankEntry {
  db_key: string
  db_label?: string | null
  rank: number
  value: number
}

export interface MetricRanking {
  metric: string
  rankings: DbRankEntry[]
  best_db_key: string
}

export interface PerTestCharts {
  bar_chart: BarChartPoint[]
  box_plot: BoxPlotPoint[]
  throughput_series: Record<string, ThroughputSeriesPoint[]>
}

export interface PerTestResult {
  analysis_mode: "per_test"
  test: ComparisonTestInfo
  warnings: AnalysisWarning[]
  descriptive_stats: Record<string, MetricStatsBundle>
  pairwise: PairwiseComparison[]
  rankings: MetricRanking[]
  charts: PerTestCharts
  analysis_report?: AnalysisReport | null
  db_key_labels: Record<string, string>
  resource_metrics: Record<string, any>
}

// ---------------------------------------------------------------------------
// Режим B: Series
// ---------------------------------------------------------------------------

export interface TrajectoryPoint {
  level_id: string
  load_label: string
  throughput_mean?: number | null
  latency_mean?: number | null
  latency_p95?: number | null
  latency_p99?: number | null
  error_rate?: number | null
  cv?: number | null
}

export interface TrendTestResult {
  statistic: number
  p_value: number
  direction: "increasing" | "decreasing" | "no_trend"
}

export interface DegradationIndex {
  p95_changes: number[]
  p99_changes: number[]
  overall_p95: number
  overall_p99: number
}

export interface DbSeriesSummary {
  db_key: string
  db_label?: string | null
  trajectory: TrajectoryPoint[]
  degradation: DegradationIndex
  stability_index?: number | null
  elasticity?: number | null
  saturation_point?: string | null
  trend_tests: Record<string, TrendTestResult>
  adjacent_level_tests: PairwiseComparison[]
  descriptive_stats_by_level: Record<string, MetricStatsBundle>
}

export interface CrossDbLevelRank {
  level_id: string
  load_label: string
  metric: string
  rankings: DbRankEntry[]
}

export interface SeriesChartPoint {
  level_id: string
  load_label: string
  value?: number | null
}

export interface SeriesCharts {
  throughput_by_load: Record<string, SeriesChartPoint[]>
  latency_by_load: Record<string, SeriesChartPoint[]>
  p95_by_load: Record<string, SeriesChartPoint[]>
  p99_by_load: Record<string, SeriesChartPoint[]>
  error_rate_by_load: Record<string, SeriesChartPoint[]>
  scaling_efficiency: Record<string, SeriesChartPoint[]>
  bar_chart: BarChartPoint[]
  box_plot: BoxPlotPoint[]
}

export interface SeriesResult {
  analysis_mode: "series"
  tests: ComparisonTestInfo[]
  baseline_id: string
  comparability: ComparabilityReport
  load_levels: LoadLevel[]
  per_db: Record<string, DbSeriesSummary>
  cross_db_ranks: CrossDbLevelRank[]
  charts: SeriesCharts
  analysis_report?: AnalysisReport | null
  db_key_labels: Record<string, string>
  parameter_impacts: ParameterImpactSummary[]
  warnings: AnalysisWarning[]
  resource_metrics: Record<string, Record<string, any>>
}

// ---------------------------------------------------------------------------
// Union-тип ответа
// ---------------------------------------------------------------------------

export type ComparisonResult = PerTestResult | SeriesResult

export function isPerTestResult(r: ComparisonResult): r is PerTestResult {
  return r.analysis_mode === "per_test"
}

export function isSeriesResult(r: ComparisonResult): r is SeriesResult {
  return r.analysis_mode === "series"
}

// ---------------------------------------------------------------------------
// API вызов
// ---------------------------------------------------------------------------

export async function analyzeComparison(request: ComparisonRequest): Promise<ComparisonResult> {
  return apiClient.analyzeComparison(request)
}
