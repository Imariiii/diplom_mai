/**
 * API клиент - Тестовые endpoints
 */

// Переиспользуем базовый клиент
import { apiClient } from "./client"

export interface TestRequest {
  query_id?: string | null
  custom_sql?: string | null
  db_types?: string[]
  connection_ids?: string[]
  /** Снимок имён подключений после разрешения connection_ids (сохраняется на сервере для истории) */
  connection_names_snapshot?: Record<string, string>
  bundle_id?: string
  resolved_bundle_id?: string
  resolved_bundle_name?: string
  resolved_profile_id?: string
  resolved_profile_name?: string
  resolved_bundle_snapshot?: {
    id?: string
    name?: string
    scenario_template_id?: string
    scenario_template_name?: string
    schema_profile_id?: string
    schema_profile_name?: string
    queries?: Array<{ sql_template?: string; query_type?: string; weight?: number }>
    indexes?: Array<Record<string, unknown>>
  }
  iterations?: number
  virtual_users?: number
  scenario?: string
  use_indexes?: boolean
  warmup_time?: number
  test_name?: string
  database_group_id?: string | null
}

export interface TestStats {
  query_id: string
  db_type: string
  iterations: number
  successful: number
  failed: number
  avg_time_ms: number
  min_time_ms: number
  max_time_ms: number
  p50_time_ms?: number
  p95_time_ms?: number
  p99_time_ms?: number
  total_time_ms: number
  tps?: number
  timestamp: string
  error?: string

  cpu_usage?: number
  memory_usage_mb?: number
  memory_usage_percent?: number
  disk_iops?: number
  network_in_mbps?: number
  network_out_mbps?: number

  cache_hit_ratio?: number
  buffer_pool_hit_ratio?: number
  lock_waits?: number
  deadlocks?: number
  active_connections?: number
  self_check?: {
    warnings?: string[]
    littles_law?: {
      valid: boolean
      reason?: string | null
      computed_concurrency?: number
      expected_concurrency?: number
      ratio?: number | null
      tolerance?: number
      warning?: string | null
    }
  }
}

export interface TestResult {
  query_id: string
  comparison: Record<string, TestStats>
  timestamp: string
}

export interface FullTestResponse {
  results: TestResult[]
  charts: {
    comparison?: string
    statistics?: string
    report?: string
  }
  summary?: {
    total_duration: number
    total_transactions: number
    total_units?: number
    workload_mode?: string
    primary_rate_unit?: string
    comparison_unit?: string
  }
}

export interface AsyncTestResponse {
  test_id: string
  name: string
  status: 'pending' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed'
  websocket_url: string
  message: string
}

export interface AsyncTestStatus {
  id: string
  name: string
  status: 'pending' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed'
  config: TestRequest
  created_at?: number
  results?: TestResult[]
  summary?: {
    total_transactions: number
    total_duration: number
    total_units?: number
    workload_mode?: string
    primary_rate_unit?: string
    comparison_unit?: string
  }
  error?: string
}

export interface HistoryTestRun {
  id: string
  name: string
  status: 'pending' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed'
  started_at: string | null
  finished_at: string | null
  config: TestRequest
  summary: {
    total_transactions?: number
    total_duration?: number
    total_units?: number
    workload_mode?: string
    primary_rate_unit?: string
    comparison_unit?: string
  } | null
  created_at: string | null
  database_group_id: string | null
}

export interface HistoryTestResult {
  id: string
  test_run_id: string
  db_type: string
  query_id: string | null
  metrics: Record<string, any> & {
    self_check?: TestStats["self_check"]
  }
  system_metrics: Record<string, number> | null
  dbms_metrics: Record<string, number> | null
  created_at: string | null
}

export interface HistoryComparison {
  test_1: HistoryTestRun & { results: HistoryTestResult[] }
  test_2: HistoryTestRun & { results: HistoryTestResult[] }
  delta: Record<string, Record<string, {
    test_1: number
    test_2: number
    diff: number
    diff_percent: number
  }>>
}

export interface HistoryErrorGroup {
  message: string
  count: number
  db_type: string | null
  query_id: string | null
  first_seen: string | null
  last_seen: string | null
  example: string | null
}

export interface HistoryErrorSample {
  id: number
  test_run_id: string
  db_type: string
  connection_key: string | null
  query_id: string | null
  sample_type: string
  timestamp: string | null
  latency_ms: number | null
  throughput: number | null
  tps: number | null
  is_error: boolean
  error_message: string | null
  created_at: string | null
}

export interface HistoryErrorReport {
  test_run_id: string
  total_errors: number
  groups: HistoryErrorGroup[]
  samples: HistoryErrorSample[]
}

// ==================== Тестовые функции ====================

export async function runAsyncTest(request: TestRequest & { test_name?: string }): Promise<AsyncTestResponse> {
  return apiClient.runAsyncTest(request)
}

export async function getAsyncTestResults(testId: string): Promise<{
  status: string
  results?: TestResult[]
  summary?: { total_transactions: number; total_duration: number }
  system_metrics?: Record<string, any>
  dbms_metrics?: Record<string, any>
  message?: string
}> {
  return apiClient.getAsyncTestResults(testId)
}

export async function cancelAsyncTest(testId: string): Promise<{
  test_id: string
  status: 'cancelling'
  message: string
}> {
  return apiClient.cancelAsyncTest(testId)
}

// ==================== История тестов ====================

export async function isHistoryEnabled(): Promise<{ enabled: boolean }> {
  return apiClient.isHistoryEnabled()
}

export async function getHistoryTests(params?: {
  limit?: number
  offset?: number
  status?: string
}): Promise<{ tests: HistoryTestRun[]; total: number }> {
  return apiClient.getHistoryTests(params)
}

export async function getHistoryTest(testId: string): Promise<HistoryTestRun & { results: HistoryTestResult[] }> {
  return apiClient.getHistoryTest(testId)
}

export async function getHistoryTestErrors(testId: string): Promise<HistoryErrorReport> {
  return apiClient.getHistoryTestErrors(testId)
}

export async function compareHistoryTests(testId1: string, testId2: string): Promise<HistoryComparison> {
  return apiClient.compareHistoryTests(testId1, testId2)
}

export async function deleteHistoryTest(testId: string): Promise<{ deleted: boolean; test_id: string }> {
  return apiClient.deleteHistoryTest(testId)
}
