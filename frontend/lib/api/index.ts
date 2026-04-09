/**
 * API модуль - главный экспорт
 * 
 * Использование:
 * import { getScenarios, getDatabaseState } from '@/lib/api'
 * или
 * import { apiClient } from '@/lib/api'
 */

// Экспорт базового клиента
export { apiClient } from './client'
export type { HealthStatus, Query } from './client'

// Экспорт тестовых функций
export {
  runAsyncTest,
  getAsyncTestResults,
  isHistoryEnabled,
  getHistoryTests,
  getHistoryTest,
  compareHistoryTests,
  deleteHistoryTest,
} from './test'
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
} from './test'

export {
  analyzeComparison,
} from './comparison'
export type {
  ComparisonRequest,
  ComparisonResult,
  ComparisonTestInfo,
  ScenarioInfo,
  ScenarioQueryInfo,
  ConnectionInfo,
  DescriptiveStats,
  MetricStatsBundle,
  PairwiseComparison,
  BarChartPoint,
  BoxPlotPoint,
  ThroughputSeriesPoint,
  ComparisonChartsData,
} from './comparison'

// Экспорт функций сценариев
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
} from './scenario'

// Экспорт функций базы данных
export {
  getDatabaseState,
  createBackup,
  restoreBackup,
  cleanupBackups,
  estimateBackup,
} from './database'

// Экспорт функций настроек
export {
  getRestoreSettings,
  updateRestoreSettings,
} from './settings'
