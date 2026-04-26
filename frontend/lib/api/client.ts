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
  ScenarioTemplate,
  ScenarioTemplateCreateRequest,
  ScenarioTemplateUpdateRequest,
  ScenarioBundleCloneRequest,
  ScenarioBundleSaveRequest,
  ScenarioBundleSummary,
  ScenarioTemplateListResponse,
  SchemaProfileListResponse,
  SchemaProfileDetail,
  ProfileBundleGenerateRequest,
  ProfileBundleGenerateResponse,
  SchemaProfileSummary,
  LogicalDatabaseListResponse,
  LogicalDatabaseDetail,
  LogicalDatabaseBundlesGenerateResponse,
  LogicalDatabaseProfileAssignRequest,
  LogicalDatabaseWithConnections,
  LogicalDatabaseCreateRequest,
  LogicalDatabaseUpdateRequest,
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
        let message: string
        if (Array.isArray(error.detail)) {
          // Pydantic validation errors (422): detail — массив объектов
          if (response.status === 422) {
            message = "Заполните все обязательные поля корректно"
          } else {
            message = (error.detail as Array<{ msg?: string }>)
              .map((e) => e.msg ?? String(e))
              .join('; ')
          }
        } else if (error.detail && typeof error.detail === 'object') {
          message = JSON.stringify(error.detail)
        } else {
          message = error.detail || `Ошибка сервера: ${response.status}`
        }
        throw new Error(message)
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
    logical_database_id?: string
  }): Promise<{ tests: any[]; total: number }> {
    const queryParams = new URLSearchParams()
    if (params?.limit) queryParams.set('limit', params.limit.toString())
    if (params?.offset) queryParams.set('offset', params.offset.toString())
    if (params?.status) queryParams.set('status', params.status)
    if (params?.logical_database_id) queryParams.set('logical_database_id', params.logical_database_id)

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

  async getHistoryTestTimeSeries(
    testId: string,
    params?: { db_type?: string; limit?: number },
  ): Promise<{ test_id: string; points: any[]; count: number }> {
    const queryParams = new URLSearchParams()
    if (params?.db_type) queryParams.set('db_type', params.db_type)
    if (params?.limit) queryParams.set('limit', params.limit.toString())
    const qs = queryParams.toString()
    return this.request(`/history/tests/${testId}/time-series${qs ? `?${qs}` : ''}`)
  }

  async analyzeComparison(request: { analysis_mode: string; test_ids: string[]; baseline_id?: string; report_config?: any }): Promise<any> {
    return this.request('/api/comparison/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    })
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

  // ==================== Логические базы данных ====================

  async getLogicalDatabases(): Promise<LogicalDatabaseListResponse> {
    return this.request<LogicalDatabaseListResponse>('/api/logical-databases/')
  }

  async getLogicalDatabaseDetail(id: string): Promise<LogicalDatabaseDetail> {
    return this.request<LogicalDatabaseDetail>(`/api/logical-databases/${id}`)
  }

  async createLogicalDatabase(data: LogicalDatabaseCreateRequest): Promise<LogicalDatabaseWithConnections> {
    return this.request<LogicalDatabaseWithConnections>('/api/logical-databases/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateLogicalDatabase(id: string, data: LogicalDatabaseUpdateRequest): Promise<LogicalDatabaseWithConnections> {
    return this.request<LogicalDatabaseWithConnections>(`/api/logical-databases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteLogicalDatabase(id: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/api/logical-databases/${id}`, {
      method: 'DELETE',
    })
  }

  async assignLogicalDatabaseProfile(
    id: string,
    data: LogicalDatabaseProfileAssignRequest
  ): Promise<LogicalDatabaseDetail> {
    return this.request<LogicalDatabaseDetail>(`/api/logical-databases/${id}/profile`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async generateLogicalDatabaseBundles(
    id: string,
    data: ProfileBundleGenerateRequest
  ): Promise<LogicalDatabaseBundlesGenerateResponse> {
    return this.request<LogicalDatabaseBundlesGenerateResponse>(`/api/logical-databases/${id}/bundles/generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // ==================== Логические сценарии и профили схем ====================

  async getScenarioTemplates(): Promise<ScenarioTemplateListResponse> {
    return this.request<ScenarioTemplateListResponse>('/api/schema-profiles/templates')
  }

  async createScenarioTemplate(data: ScenarioTemplateCreateRequest): Promise<ScenarioTemplate> {
    return this.request<ScenarioTemplate>(`/api/schema-profiles/templates`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateScenarioTemplate(templateId: string, data: ScenarioTemplateUpdateRequest): Promise<ScenarioTemplate> {
    return this.request<ScenarioTemplate>(`/api/schema-profiles/templates/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteScenarioTemplate(templateId: string): Promise<{ deleted: boolean; template_id: string }> {
    return this.request(`/api/schema-profiles/templates/${templateId}`, {
      method: 'DELETE',
    })
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

  async createBundleVariant(
    profileId: string,
    data: ScenarioBundleSaveRequest
  ): Promise<ScenarioBundleSummary> {
    return this.request<ScenarioBundleSummary>(`/api/schema-profiles/${profileId}/bundles`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getBundleVariant(profileId: string, bundleId: string): Promise<ScenarioBundleSummary> {
    return this.request<ScenarioBundleSummary>(`/api/schema-profiles/${profileId}/bundles/${bundleId}`)
  }

  async updateBundleVariant(
    profileId: string,
    bundleId: string,
    data: ScenarioBundleSaveRequest
  ): Promise<ScenarioBundleSummary> {
    return this.request<ScenarioBundleSummary>(`/api/schema-profiles/${profileId}/bundles/${bundleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async cloneBundleVariant(
    profileId: string,
    bundleId: string,
    data: ScenarioBundleCloneRequest
  ): Promise<ScenarioBundleSummary> {
    return this.request<ScenarioBundleSummary>(`/api/schema-profiles/${profileId}/bundles/${bundleId}/clone`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async activateBundleVariant(profileId: string, bundleId: string): Promise<ScenarioBundleSummary> {
    return this.request<ScenarioBundleSummary>(`/api/schema-profiles/${profileId}/bundles/${bundleId}/activate`, {
      method: 'POST',
    })
  }

  async deleteBundleVariant(profileId: string, bundleId: string): Promise<{ deleted: boolean; bundle_id: string }> {
    return this.request<{ deleted: boolean; bundle_id: string }>(`/api/schema-profiles/${profileId}/bundles/${bundleId}`, {
      method: 'DELETE',
    })
  }
}

export const apiClient = new ApiClient()
