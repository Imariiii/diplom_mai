/**
 * API клиент для работы с backend
 */

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
  total_time_ms: number
  timestamp: string
  error?: string
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
}

export const apiClient = new ApiClient()

