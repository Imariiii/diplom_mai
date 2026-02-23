/**
 * API клиент для работы с backend
 */

import type { TestScenario } from "./types"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface HealthStatus {
  status: string
  mysql: 'connected' | 'disconnected'
  postgresql: 'connected' | 'disconnected'
}

export interface Query {
  id: string
  name: string
  sql: string
  description: string
}

export interface TestRequest {
  query_id?: string | null
  db_types?: string[]
  iterations?: number
  virtual_users?: number      // Количество виртуальных пользователей
  scenario?: TestScenario     // Сценарий тестирования
  warmup_time?: number        // Время прогрева в секундах
  test_name?: string          // Название теста
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
  p50_time_ms?: number        // Медиана
  p95_time_ms?: number        // 95-й перцентиль
  p99_time_ms?: number        // 99-й перцентиль
  total_time_ms: number
  tps?: number                // Транзакций в секунду
  timestamp: string
  error?: string
  
  // Системные метрики
  cpu_usage?: number
  memory_usage_mb?: number
  memory_usage_percent?: number
  disk_iops?: number
  network_in_mbps?: number
  network_out_mbps?: number
  
  // Внутренние метрики СУБД
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

// Типы для асинхронного теста
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

// Типы для истории тестов
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

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(error.detail || `HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error)
      throw error
    }
  }

  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health')
  }

  async getQueries(): Promise<Query[]> {
    return this.request<Query[]>('/queries')
  }

  async getQuery(queryId: string): Promise<Query> {
    return this.request<Query>(`/queries/${queryId}`)
  }

  async runSingleTest(request: TestRequest): Promise<TestResult> {
    return this.request<TestResult>('/test/single', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async runFullTest(request: TestRequest): Promise<FullTestResponse> {
    return this.request<FullTestResponse>('/test/full', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getCharts(): Promise<{ charts: Array<{ filename: string; path: string }> }> {
    return this.request<{ charts: Array<{ filename: string; path: string }> }>('/results/charts')
  }

  async getSystemMetrics(dbType: string): Promise<{
    cpu_usage: number
    memory_usage_mb: number
    memory_usage_percent: number
    disk_iops: number
    network_in_mbps: number
    network_out_mbps: number
  }> {
    return this.request(`/metrics/system/${dbType}`)
  }

  async getDBMSMetrics(dbType: string): Promise<{
    cache_hit_ratio: number
    buffer_pool_hit_ratio: number
    lock_waits: number
    deadlocks: number
    active_connections: number
    table_sizes_mb: Record<string, number>
    index_sizes_mb: Record<string, number>
    total_db_size_mb: number
  }> {
    return this.request(`/metrics/dbms/${dbType}`)
  }

  // ==================== Асинхронное тестирование ====================

  async runAsyncTest(request: TestRequest & { test_name?: string }): Promise<AsyncTestResponse> {
    return this.request<AsyncTestResponse>('/test/async', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getAsyncTestStatus(testId: string): Promise<AsyncTestStatus> {
    return this.request<AsyncTestStatus>(`/test/async/${testId}`)
  }

  async getAsyncTestResults(testId: string): Promise<{
    status: string
    results?: TestResult[]
    summary?: { total_transactions: number; overall_tps: number; total_duration: number }
    system_metrics?: Record<string, any>
    dbms_metrics?: Record<string, any>
    message?: string
  }> {
    return this.request(`/test/async/${testId}/results`)
  }

  async getWebSocketConnections(): Promise<{
    total_connections: number
    active_tests: string[]
  }> {
    return this.request('/ws/connections')
  }

  // ==================== История тестов ====================

  async isHistoryEnabled(): Promise<{ enabled: boolean }> {
    return this.request<{ enabled: boolean }>('/history/enabled')
  }

  async getHistoryTests(params?: {
    limit?: number
    offset?: number
    status?: string
  }): Promise<{ tests: HistoryTestRun[]; total: number }> {
    const queryParams = new URLSearchParams()
    if (params?.limit) queryParams.set('limit', params.limit.toString())
    if (params?.offset) queryParams.set('offset', params.offset.toString())
    if (params?.status) queryParams.set('status', params.status)
    
    const queryString = queryParams.toString()
    return this.request(`/history/tests${queryString ? `?${queryString}` : ''}`)
  }

  async getHistoryTest(testId: string): Promise<HistoryTestRun & { results: HistoryTestResult[] }> {
    return this.request(`/history/tests/${testId}`)
  }

  async getHistoryTimeSeries(testId: string, dbType?: string, limit?: number): Promise<{
    timeseries: Array<{
      id: number
      test_run_id: string
      db_type: string
      timestamp: string
      response_time: number | null
      tps: number | null
      throughput: number | null
      active_connections: number | null
      error_count: number
      cpu_usage: number | null
      memory_usage: number | null
      memory_usage_mb: number | null
      disk_iops: number | null
      network_in: number | null
      network_out: number | null
    }>
  }> {
    const queryParams = new URLSearchParams()
    if (dbType) queryParams.set('db_type', dbType)
    if (limit) queryParams.set('limit', limit.toString())
    
    const queryString = queryParams.toString()
    return this.request(`/history/tests/${testId}/timeseries${queryString ? `?${queryString}` : ''}`)
  }

  async compareHistoryTests(testId1: string, testId2: string): Promise<HistoryComparison> {
    return this.request(`/history/compare/${testId1}/${testId2}`)
  }

  async deleteHistoryTest(testId: string): Promise<{ deleted: boolean; test_id: string }> {
    return this.request(`/history/tests/${testId}`, { method: 'DELETE' })
  }

  async getHistoryStatistics(): Promise<{
    total_runs: number
    completed_runs: number
    failed_runs: number
    success_rate: number
  }> {
    return this.request('/history/statistics')
  }
}

export const apiClient = new ApiClient()
