/**
 * Canonical API entrypoint для frontend
 */

// Реэкспорт из модульной структуры
export { apiClient } from "./api/client"
export type { HealthStatus } from "./api/client"

// Типы - реэкспорт из database
// (функции возвращают Promise с inline типами, отдельные типы не требуются)

// Типы - реэкспорт из test
export type {
  TestRequest,
  TestStats,
  TestResult,
  FullTestResponse,
  AsyncTestResponse,
  AsyncTestStatus,
  HistoryTestRun,
  HistoryTestResult,
  HistoryComparison,
  HistoryErrorReport,
  HistoryErrorGroup,
  HistoryErrorSample,
} from "./api/test"

export type {
  AnalysisMode,
  ComparisonRequest,
  ComparisonResult,
  ComparisonTestInfo,
  ScenarioInfo,
  ScenarioQueryInfo,
  ConnectionInfo,
  AnalysisReport,
  AnalysisReportConfig,
  AnalysisSection,
  AnalysisWarning,
  WarningSeverity,
  ComparabilityReport,
  LoadLevel,
  DescriptiveStats,
  MetricStatsBundle,
  PairwiseComparison,
  BarChartPoint,
  BoxPlotPoint,
  ThroughputSeriesPoint,
  ChangedParameter,
  MetricEffect,
  MetricEffectMetric,
  MetricEffectDirection,
  MetricEffectMagnitude,
  ParameterImpactSummary,
  ResourceMetrics,
  PerTestResult,
  PerTestCharts,
  DbRankEntry,
  MetricRanking,
  SeriesResult,
  SeriesCharts,
  SeriesChartPoint,
  TrajectoryPoint,
  TrendTestResult,
  DegradationIndex,
  DbSeriesSummary,
  CrossDbLevelRank,
  DbFinding,
  DbFindingStatus,
  DbMetricChip,
  DbMetricChipTone,
} from "./api/comparison"

// Функции и type guards - реэкспорт из модулей
export {
  runAsyncTest,
  getAsyncTestResults,
  isHistoryEnabled,
  getHistoryTests,
  getHistoryTest,
  getHistoryTestErrors,
  compareHistoryTests,
  deleteHistoryTest,
} from "./api/test"

export {
  analyzeComparison,
  isPerTestResult,
  isSeriesResult,
} from "./api/comparison"

export {
  getDatabaseState,
  createBackup,
  restoreBackup,
  cleanupBackups,
  estimateBackup,
} from "./api/database"

export {
  getRestoreSettings,
  updateRestoreSettings,
} from "./api/settings"
