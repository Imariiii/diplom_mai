/**
 * Базовый API клиент
 */

import type {
  DatabaseConnection,
  ConnectionCreateRequest,
  ConnectionUpdateRequest,
  ConnectionTestRequest,
  ConnectionTestResponse,
  ConnectionListResponse,
  ConnectionGroupsResponse,
  ConnectionSchemaPreview,
  ConnectionProfileAssignRequest,
  GenerateScenariosRequest,
  GenerateScenariosResponse,
  CreateScenarioIndexRequest,
  ScenarioIndex,
  ScenarioTemplateListResponse,
  SchemaProfileListResponse,
  SchemaProfileDetail,
  ProfileBundleGenerateRequest,
  ProfileBundleGenerateResponse,
  SchemaProfileSummary,
} from '@/lib/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface HealthStatus {
  status: string
  api: 'connected' | 'disconnected'
  history_db: 'connected' | 'disconnected'
}

export interface Query {
  id: string
  name: string
  sql: string
  description: string
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const hasBody = options?.body !== undefined
    const headers = {
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      ...options?.headers,
    }
    
    try {
      const response = await fetch(url, {
        ...options,
        headers,
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

  // ==================== Общие методы ====================

  async getHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health')
  }

  async getQueries(): Promise<Query[]> {
    return this.request<Query[]>('/queries')
  }

  // ==================== Асинхронное тестирование ====================

  async runAsyncTest(request: any): Promise<any> {
    return this.request('/test/async', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getAsyncTestResults(testId: string): Promise<any> {
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
  }): Promise<{ tests: any[]; total: number }> {
    const queryParams = new URLSearchParams()
    if (params?.limit) queryParams.set('limit', params.limit.toString())
    if (params?.offset) queryParams.set('offset', params.offset.toString())
    if (params?.status) queryParams.set('status', params.status)
    
    const queryString = queryParams.toString()
    return this.request(`/history/tests${queryString ? `?${queryString}` : ''}`)
  }

  async getHistoryTest(testId: string): Promise<any> {
    return this.request(`/history/tests/${testId}`)
  }

  async compareHistoryTests(testId1: string, testId2: string): Promise<any> {
    return this.request(`/history/compare/${testId1}/${testId2}`)
  }

  async deleteHistoryTest(testId: string): Promise<{ deleted: boolean; test_id: string }> {
    return this.request(`/history/tests/${testId}`, { method: 'DELETE' })
  }

  async analyzeComparison(request: { test_ids: string[]; baseline_id?: string }): Promise<any> {
    return this.request('/api/comparison/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // ==================== Сценарии тестирования ====================

  async getScenarios(params?: {
    targetConnectionId?: string
    includeGlobal?: boolean
    includeBuiltin?: boolean
  }): Promise<{ scenarios: any[] }> {
    const queryParams = new URLSearchParams()
    if (params?.targetConnectionId) queryParams.set('target_connection_id', params.targetConnectionId)
    if (params?.includeGlobal !== undefined) queryParams.set('include_global', String(params.includeGlobal))
    if (params?.includeBuiltin !== undefined) queryParams.set('include_builtin', String(params.includeBuiltin))
    const queryString = queryParams.toString()
    return this.request(`/scenarios${queryString ? `?${queryString}` : ''}`)
  }

  async getScenario(id: string): Promise<any> {
    return this.request(`/scenarios/${id}`)
  }

  async getEnabledScenarios(): Promise<{ scenarios: any[] }> {
    return this.request('/scenarios')
  }

  async createScenario(scenario: any): Promise<any> {
    return this.request('/scenarios', {
      method: 'POST',
      body: JSON.stringify(scenario),
    })
  }

  async updateScenario(id: string, scenario: any): Promise<any> {
    return this.request(`/scenarios/${id}`, {
      method: 'PUT',
      body: JSON.stringify(scenario),
    })
  }

  async deleteScenario(id: string): Promise<{ deleted: boolean; scenario_id: string }> {
    return this.request(`/scenarios/${id}`, { method: 'DELETE' })
  }

  async cloneScenario(id: string, newName?: string): Promise<any> {
    return this.request(`/scenarios/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName }),
    })
  }

  async generateScenarios(data: GenerateScenariosRequest): Promise<GenerateScenariosResponse> {
    return this.request<GenerateScenariosResponse>('/scenarios/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Индексы сценария
  async getScenarioIndexes(scenarioId: string): Promise<{ indexes: ScenarioIndex[] }> {
    return this.request(`/scenarios/${scenarioId}/indexes`)
  }

  async createScenarioIndex(scenarioId: string, index: CreateScenarioIndexRequest): Promise<ScenarioIndex> {
    return this.request(`/scenarios/${scenarioId}/indexes`, {
      method: 'POST',
      body: JSON.stringify(index),
    })
  }

  async updateScenarioIndex(scenarioId: string, indexId: string, index: Partial<CreateScenarioIndexRequest>): Promise<ScenarioIndex> {
    return this.request(`/scenarios/${scenarioId}/indexes/${indexId}`, {
      method: 'PUT',
      body: JSON.stringify(index),
    })
  }

  async deleteScenarioIndex(scenarioId: string, indexId: string): Promise<{ deleted: boolean; index_id: string }> {
    return this.request(`/scenarios/${scenarioId}/indexes/${indexId}`, { method: 'DELETE' })
  }

  // Запросы сценария
  async getScenarioQueries(scenarioId: string): Promise<{ queries: any[] }> {
    return this.request(`/scenarios/${scenarioId}/queries`)
  }

  async createScenarioQuery(scenarioId: string, query: any): Promise<any> {
    return this.request(`/scenarios/${scenarioId}/queries`, {
      method: 'POST',
      body: JSON.stringify(query),
    })
  }

  async updateScenarioQuery(scenarioId: string, queryId: string, query: any): Promise<any> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}`, {
      method: 'PUT',
      body: JSON.stringify(query),
    })
  }

  async deleteScenarioQuery(scenarioId: string, queryId: string): Promise<{ deleted: boolean; query_id: string }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}`, { method: 'DELETE' })
  }

  // Параметры запроса
  async getScenarioQueryParams(scenarioId: string, queryId: string): Promise<{ params: any[] }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params`)
  }

  async createScenarioParam(scenarioId: string, queryId: string, param: any): Promise<any> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params`, {
      method: 'POST',
      body: JSON.stringify(param),
    })
  }

  async updateScenarioParam(scenarioId: string, queryId: string, paramId: string, param: any): Promise<any> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params/${paramId}`, {
      method: 'PUT',
      body: JSON.stringify(param),
    })
  }

  async deleteScenarioParam(scenarioId: string, queryId: string, paramId: string): Promise<{ deleted: boolean; param_id: string }> {
    return this.request(`/scenarios/${scenarioId}/queries/${queryId}/params/${paramId}`, { method: 'DELETE' })
  }

  // ==================== Database State Management ====================

  async getDatabaseState(connectionId: string): Promise<any> {
    return this.request(`/api/database/connections/${connectionId}/state`)
  }

  async createBackup(connectionId: string, tables?: string[]): Promise<any> {
    const body = tables ? { tables } : {}
    return this.request(`/api/database/connections/${connectionId}/backup`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async restoreBackup(connectionId: string, backupId?: string): Promise<any> {
    const body = backupId ? { backup_id: backupId } : {}
    return this.request(`/api/database/connections/${connectionId}/restore`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  async cleanupBackups(connectionId: string): Promise<{ deleted_tables: string[] }> {
    return this.request(`/api/database/connections/${connectionId}/cleanup`, {
      method: 'POST',
    })
  }

  async estimateBackup(connectionId: string, tables: string[]): Promise<any> {
    const params = new URLSearchParams({ tables: tables.join(',') })
    return this.request(`/api/database/connections/${connectionId}/estimate?${params}`)
  }

  // ==================== Настройки ====================

  async getRestoreSettings(): Promise<any> {
    return this.request('/api/settings/restore')
  }

  async updateRestoreSettings(settings: any): Promise<any> {
    return this.request('/api/settings/restore', {
      method: 'PUT',
      body: JSON.stringify(settings),
    })
  }

  // ==================== Управление подключениями ====================

  async getConnections(group?: string): Promise<ConnectionListResponse> {
    const params = group ? `?group=${encodeURIComponent(group)}` : ''
    return this.request<ConnectionListResponse>(`/api/connections/${params}`)
  }

  async getConnectionGroups(): Promise<ConnectionGroupsResponse> {
    return this.request<ConnectionGroupsResponse>('/api/connections/groups')
  }

  async getConnection(id: string): Promise<DatabaseConnection> {
    return this.request<DatabaseConnection>(`/api/connections/${id}`)
  }

  async getConnectionSchema(id: string): Promise<ConnectionSchemaPreview> {
    return this.request<ConnectionSchemaPreview>(`/api/connections/${id}/schema`)
  }

  async assignConnectionProfile(id: string, data: ConnectionProfileAssignRequest): Promise<DatabaseConnection> {
    return this.request<DatabaseConnection>(`/api/connections/${id}/profile`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async createConnection(data: ConnectionCreateRequest): Promise<DatabaseConnection> {
    return this.request<DatabaseConnection>('/api/connections', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateConnection(id: string, data: ConnectionUpdateRequest): Promise<DatabaseConnection> {
    return this.request<DatabaseConnection>(`/api/connections/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteConnection(id: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/api/connections/${id}`, {
      method: 'DELETE',
    })
  }

  async testConnection(data: ConnectionTestRequest): Promise<ConnectionTestResponse> {
    return this.request<ConnectionTestResponse>('/api/connections/test', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async testSavedConnection(id: string): Promise<ConnectionTestResponse> {
    return this.request<ConnectionTestResponse>(`/api/connections/${id}/test`, {
      method: 'POST',
    })
  }

  // ==================== Логические сценарии и профили схем ====================

  async getScenarioTemplates(): Promise<ScenarioTemplateListResponse> {
    return this.request<ScenarioTemplateListResponse>('/api/schema-profiles/templates')
  }

  async getSchemaProfiles(): Promise<SchemaProfileListResponse> {
    return this.request<SchemaProfileListResponse>('/api/schema-profiles')
  }

  async getSchemaProfile(profileId: string): Promise<SchemaProfileDetail> {
    return this.request<SchemaProfileDetail>(`/api/schema-profiles/${profileId}`)
  }

  async createSchemaProfile(data: {
    name: string
    description?: string
    reference_connection_id?: string
  }): Promise<SchemaProfileSummary> {
    return this.request<SchemaProfileSummary>('/api/schema-profiles', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async generateProfileBundles(
    profileId: string,
    data: ProfileBundleGenerateRequest
  ): Promise<ProfileBundleGenerateResponse> {
    return this.request<ProfileBundleGenerateResponse>(`/api/schema-profiles/${profileId}/bundles/generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
}

export const apiClient = new ApiClient()
