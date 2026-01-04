export interface Database {
  id: string
  name: string
  type: "postgresql" | "mysql" | "mariadb" | "sqlite" | "mssql"
  icon: string
}

export interface TestConfig {
  databases: string[]
  concurrentUsers: number
  testDuration: number
  queryTypes: ("read" | "write" | "mixed")[]
  dataSize: "small" | "medium" | "large"
}

export interface TestRun {
  id: string
  name: string
  status: "pending" | "running" | "completed" | "failed"
  startTime: Date
  endTime?: Date
  config: TestConfig
  results?: TestResult[]
}

export interface TestResult {
  databaseId: string
  metrics: {
    avgResponseTime: number
    maxResponseTime: number
    minResponseTime: number
    throughput: number
    errorRate: number
    p95ResponseTime: number
    p99ResponseTime: number
  }
  timeSeriesData: TimeSeriesPoint[]
}

export interface TimeSeriesPoint {
  timestamp: number
  responseTime: number
  throughput: number
  activeConnections: number
  cpuUsage: number
  memoryUsage: number
}
