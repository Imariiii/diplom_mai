/**
 * API клиент - Тестовые endpoints
 */

// Переиспользуем базовый клиент
import { apiClient } from "./client"

export interface TestRequest {
  query_id?: string | null
  db_types?: string[]
  connection_ids?: string[]
  bundle_id?: string
  iterations?: number
  virtual_users?: number
  scenario?: string
  use_indexes?: boolean
  warmup_time?: number
  test_name?: string
  logical_database_id?: string | null
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
    overall_tps: number
  }
}

export interface AsyncTestResponse {
  test_id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  websocket_url: string
  message: string
}

export interface AsyncTestStatus {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  config: TestRequest
  created_at?: number
  results?: TestResult[]
  summary?: {
    total_transactions: number
    overall_tps: number
    total_duration: number
  }
  error?: string
}

export interface HistoryTestRun {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at: string | null
  finished_at: string | null
  config: TestRequest
  summary: {
    total_transactions?: number
    overall_tps?: number
    total_duration?: number
  } | null
  created_at: string | null
  logical_database_id: string | null
}

export interface HistoryTestResult {
  id: string
  test_run_id: string
  db_type: string
  query_id: string | null
  metrics: Record<string, number>
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

// ==================== Тестовые функции ====================

export async function runAsyncTest(request: TestRequest & { test_name?: string }): Promise<AsyncTestResponse> {
  return apiClient.runAsyncTest(request)
}

export async function getAsyncTestResults(testId: string): Promise<{
  status: string
  results?: TestResult[]
  summary?: { total_transactions: number; overall_tps: number; total_duration: number }
  system_metrics?: Record<string, any>
  dbms_metrics?: Record<string, any>
  message?: string
}> {
  return apiClient.getAsyncTestResults(testId)
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

export async function compareHistoryTests(testId1: string, testId2: string): Promise<HistoryComparison> {
  return apiClient.compareHistoryTests(testId1, testId2)
}

export async function deleteHistoryTest(testId: string): Promise<{ deleted: boolean; test_id: string }> {
  return apiClient.deleteHistoryTest(testId)
}