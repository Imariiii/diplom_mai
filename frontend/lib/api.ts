/**
 * API клиент для работы с backend
 */

import type {
  Scenario,
  ScenarioQuery,
  ScenarioParam,
  CreateScenarioRequest,
  CreateScenarioQueryRequest,
  CreateScenarioParamRequest,
} from "./types"

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
  scenario?: string           // ID сценария тестирования (UUID из БД или строковый сценарий)
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

  // ==================== Асинхронное тестирование ====================

  async runAsyncTest(request: TestRequest & { test_name?: string }): Promise<AsyncTestResponse> {
    return this.request<AsyncTestResponse>('/test/async', {
      method: 'POST',
      body: JSON.stringify(request),
    })
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

  async compareHistoryTests(testId1: string, testId2: string): Promise<HistoryComparison> {
    return this.request(`/history/compare/${testId1}/${testId2}`)
  }

  async deleteHistoryTest(testId: string): Promise<{ deleted: boolean; test_id: string }> {
    return this.request(`/history/tests/${testId}`, { method: 'DELETE' })
  }

  // ==================== Сценарии тестирования ====================

  async getScenarios(): Promise<{ scenarios: Scenario[] }> {
    return this.request('/scenarios')
  }

  async getScenario(id: string): Promise<Scenario> {
    return this.request(`/scenarios/${id}`)
  }

  async getEnabledScenarios(): Promise<{ scenarios: Scenario[] }> {
    return this.request('/scenarios')
  }

  async createScenario(scenario: CreateScenarioRequest): Promise<Scenario> {
    return this.request('/scenarios', {
      method: 'POST',
      body: JSON.stringify(scenario),
    })
  }

  async updateScenario(id: string, scenario: Partial<CreateScenarioRequest>): Promise<Scenario> {
    return this.request(`/scenarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify(scenario),
    })
  }

  async deleteScenario(id: string): Promise<{ deleted: boolean; scenario_id: string }> {
    return this.request(`/scenarios/${id}`, { method: 'DELETE' })
  }

  async cloneScenario(id: string, newName?: string): Promise<Scenario> {
    return this.request(`/scenarios/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName }),
    })
  }

  // Запросы сценария
  async getScenarioQueries(scenarioId: string): Promise<{ queries: ScenarioQuery[] }> {
    return this.request(`/scenarios/${scenarioId}/queries`)
  }

  async createScenarioQuery(scenarioId: string, query: CreateScenarioQueryRequest): Promise<ScenarioQuery> {
    return this.request(`/scenarios/${scenarioId}/queries`, {
      method: 'POST',
      body: JSON.stringify(query),
    })
  }

  async updateScenarioQuery(
    scenarioId: string,
    queryId: string,
    query: Partial<CreateScenarioQueryRequest>
  ): Promise<ScenarioQuery> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}`, {
      method: 'PUT',
      body: JSON.stringify(query),
    })
  }

  async deleteScenarioQuery(scenarioId: string, queryId: string): Promise<{ deleted: boolean; query_id: string }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}`, { method: 'DELETE' })
  }

  // Параметры запроса
  async getScenarioQueryParams(scenarioId: string, queryId: string): Promise<{ params: ScenarioParam[] }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params`)
  }

  async createScenarioParam(
    scenarioId: string,
    queryId: string,
    param: CreateScenarioParamRequest
  ): Promise<ScenarioParam> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params`, {
      method: 'POST',
      body: JSON.stringify(param),
    })
  }

  async updateScenarioParam(
    scenarioId: string,
    queryId: string,
    paramId: string,
    param: Partial<CreateScenarioParamRequest>
  ): Promise<ScenarioParam> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params/${paramId}`, {
      method: 'PUT',
      body: JSON.stringify(param),
    })
  }

  async deleteScenarioParam(
    scenarioId: string,
    queryId: string,
    paramId: string
  ): Promise<{ deleted: boolean; param_id: string }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params/${paramId}`, { method: 'DELETE' })
  }

  // ==================== Database State Management ====================

  async getDatabaseState(dbmsType: string): Promise<{
    dbms_type: string
    tables: Record<string, { row_count: number; has_backup: boolean }>
    has_pending_backups: boolean
    backup_tables: string[]
    status: 'clean' | 'modified' | 'backup_exists'
  }> {
    return this.request(`/api/database/${dbmsType}/state`)
  }

  async createBackup(dbmsType: string, tables?: string[]): Promise<{
    backup_id: string
    dbms_type: string
    tables: string[]
    row_counts: Record<string, number>
    created_at: string
  }> {
    return this.request(`/api/database/${dbmsType}/backup`, {
      method: 'POST',
      body: JSON.stringify({ tables }),
    })
  }

  async restoreBackup(dbmsType: string, backupId?: string): Promise<{
    success: boolean
    duration_ms: number
    verified: boolean
    errors: string[]
  }> {
    return this.request(`/api/database/${dbmsType}/restore`, {
      method: 'POST',
      body: JSON.stringify({ backup_id: backupId }),
    })
  }

  async cleanupBackups(dbmsType: string): Promise<{
    deleted_tables: string[]
  }> {
    return this.request(`/api/database/${dbmsType}/cleanup`, {
      method: 'POST',
    })
  }

  async estimateBackup(dbmsType: string, tables: string[]): Promise<{
    tables: Record<string, { rows: number; size_bytes: number }>
    total_rows: number
    total_size_bytes: number
    estimated_time_sec: number
    warnings: string[]
  }> {
    const params = new URLSearchParams({ tables: tables.join(',') })
    return this.request(`/api/database/${dbmsType}/estimate?${params}`)
  }

  async getRestoreSettings(): Promise<{
    auto_restore: boolean
    verify_after_restore: boolean
    strategy: 'sql' | 'native'
    large_table_warning_threshold: number
    large_table_confirm_threshold: number
    backup_table_prefix: string
  }> {
    return this.request('/api/settings/restore')
  }

  async updateRestoreSettings(settings: {
    auto_restore?: boolean
    verify_after_restore?: boolean
    strategy?: 'sql' | 'native'
    large_table_warning_threshold?: number
  }): Promise<{
    auto_restore: boolean
    verify_after_restore: boolean
    strategy: 'sql' | 'native'
    large_table_warning_threshold: number
  }> {
    return this.request('/api/settings/restore', {
      method: 'PUT',
      body: JSON.stringify(settings),
    })
  }
}

export const apiClient = new ApiClient()
