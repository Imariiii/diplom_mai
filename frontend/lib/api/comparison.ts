/**
 * API клиент - Сравнение тестов
 */
import { apiClient } from "./client"

export interface ComparisonRequest {
  test_ids: string[]
  baseline_id?: string
  report_config?: AnalysisReportConfig
}

export type ComparisonType =
  | "cross_database"
  | "scalability"
  | "mixed"
  | "temporal"

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

export interface NormalizedMetrics {
  throughput_abs?: number | null
  latency_mean_abs?: number | null
  throughput_per_thread?: number | null
  throughput_per_second?: number | null
  scaling_efficiency?: number | null
  latency_per_thread?: number | null
  threads?: number | null
  duration_seconds?: number | null
  source_metrics: string[]
  normalization_warning?: string | null
}

export interface PairwiseComparison {
  baseline_test_id: string
  compared_test_id: string
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
}

export interface BarChartPoint {
  test_id: string
  test_name: string
  db_key: string
  latency_mean?: number | null
  latency_p95?: number | null
  latency_p99?: number | null
  throughput_mean?: number | null
  error_rate?: number | null
}

export interface BoxPlotPoint {
  test_id: string
  test_name: string
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

export interface ComparisonChartsData {
  bar_chart: BarChartPoint[]
  box_plot: BoxPlotPoint[]
  throughput_series: Record<string, ThroughputSeriesPoint[]>
}

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

export interface AnalysisReportConfig {
  include_verdict: boolean
  include_patterns: boolean
  include_recommendations: boolean
  include_hypotheses: boolean
}

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

export interface ComparisonResult {
  tests: ComparisonTestInfo[]
  baseline_id: string
  comparison_type: ComparisonType
  warnings: string[]
  descriptive_stats: Record<string, Record<string, MetricStatsBundle>>
  normalized_metrics: Record<string, Record<string, NormalizedMetrics>>
  pairwise_comparisons: PairwiseComparison[]
  charts_data: ComparisonChartsData
  analysis_report?: AnalysisReport | null
  db_key_labels: Record<string, string>
  parameter_impacts: ParameterImpactSummary[]
}

export async function analyzeComparison(request: ComparisonRequest): Promise<ComparisonResult> {
  return apiClient.analyzeComparison(request)
}
