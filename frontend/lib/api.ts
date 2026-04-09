/**
 * API клиент для работы с backend
 * 
 * Этот файл сохраняет обратную совместимость.
 * Новый код рекомендуется импортировать из '@/lib/api'
 * 
 * @deprecated Используйте import из '@/lib/api'
 */

import type {
  Scenario,
  ScenarioQuery,
  ScenarioParam,
  CreateScenarioRequest,
  CreateScenarioQueryRequest,
  CreateScenarioParamRequest,
} from "./types"

// Реэкспорт из новой модульной структуры для обратной совместимости
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
  getScenarios,
  getScenario,
  getEnabledScenarios,
  createScenario,
  updateScenario,
  deleteScenario,
  cloneScenario,
  getScenarioQueries,
  createScenarioQuery,
  updateScenarioQuery,
  deleteScenarioQuery,
  getScenarioQueryParams,
  createScenarioParam,
  updateScenarioParam,
  deleteScenarioParam,
} from "./api/scenario"

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
