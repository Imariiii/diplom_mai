/**
 * Canonical API entrypoint для frontend
 */

// Реэкспорт из модульной структуры
export { apiClient } from "./api/client"
export type { HealthStatus, Query } from "./api/client"

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
} from "./api/test"

export type {
  ComparisonRequest,
  ComparisonType,
  ComparisonResult,
  ComparisonTestInfo,
  ScenarioInfo,
  ScenarioQueryInfo,
  ConnectionInfo,
  AnalysisReport,
  AnalysisReportConfig,
  AnalysisSection,
  DescriptiveStats,
  MetricStatsBundle,
  NormalizedMetrics,
  PairwiseComparison,
  BarChartPoint,
  BoxPlotPoint,
  ThroughputSeriesPoint,
  ComparisonChartsData,
  ParameterImpact,
  ParameterImpactSummary,
} from "./api/comparison"

// Функции - реэкспорт из модулей
export {
  runAsyncTest,
  getAsyncTestResults,
  isHistoryEnabled,
  getHistoryTests,
  getHistoryTest,
  compareHistoryTests,
  deleteHistoryTest,
} from "./api/test"

export {
  analyzeComparison,
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
