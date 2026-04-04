"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Database, Clock, Gauge, Users, AlertTriangle } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { TimeSeriesChart } from "./shared/time-series-chart"

interface TestResult {
  databaseId: string
  metrics?: {
    avgResponseTime?: number
    p50ResponseTime?: number
    p95ResponseTime?: number
    p99ResponseTime?: number
    minResponseTime?: number
    maxResponseTime?: number
    tps?: number
    throughput?: number
    activeConnections?: number
    errorCount?: number
  }
}

interface DatabaseMetricsTabProps {
  databases: string[]
  chartData: Record<string, unknown>[]
  getResultForDb: (dbId: string) => TestResult | undefined
  getLatestMetric: (dbId: string, metric: string) => string
  getDbDisplayName: (dbId: string) => string
  getDbType: (dbKey: string) => string
  virtualUsers: number
  customDbNames?: Record<string, string>
}

export function DatabaseMetricsTab({ databases, chartData, getResultForDb, getLatestMetric, getDbDisplayName, getDbType, virtualUsers, customDbNames }: DatabaseMetricsTabProps) {
  const formatMetric = (value?: number, digits: number = 2) => {
    return typeof value === "number" ? value.toFixed(digits) : undefined
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {databases.map((dbId) => {
          const result = getResultForDb(dbId)
          const dbType = getDbType(dbId)
          return (
            <Card key={dbId} className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-foreground">
                  <Database className="h-4 w-4" style={{ color: getDbColor(dbType) }} />
                  {getDbDisplayName(dbId)}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Avg время</span>
                  <span className="font-mono text-foreground">{formatMetric(result?.metrics?.avgResponseTime) ?? getLatestMetric(dbId, "responseTime")} ms</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">TPS</span>
                  <span className="font-mono text-foreground">{formatMetric(result?.metrics?.tps, 0) ?? getLatestMetric(dbId, "tps")} tx/s</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Соединения</span>
                  <span className="font-mono text-foreground">{result?.metrics?.activeConnections || virtualUsers}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Ошибки</span>
                  <span className="font-mono text-foreground">{result?.metrics?.errorCount || 0}</span>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground">
            <Clock className="h-5 w-5 text-primary" />
            Время отклика (перцентили)
          </CardTitle>
          <CardDescription>avg, p50, p95, p99 для каждой СУБД</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {databases.map((dbId) => {
              const result = getResultForDb(dbId)
              const metrics = result?.metrics
              const dbType = getDbType(dbId)
              return (
                <div key={dbId} className="p-4 bg-muted rounded-lg">
                  <div className="font-medium mb-3 text-foreground" style={{ color: getDbColor(dbType) }}>
                    {getDbDisplayName(dbId)}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Avg:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.avgResponseTime) ?? "—"} ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">p50:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.p50ResponseTime) ?? "—"} ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">p95:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.p95ResponseTime) ?? "—"} ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">p99:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.p99ResponseTime) ?? "—"} ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Min:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.minResponseTime) ?? "—"} ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Max:</span>
                      <span className="font-mono text-foreground">{formatMetric(metrics?.maxResponseTime) ?? "—"} ms</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TimeSeriesChart
          title="Время отклика (ms)"
          icon={<Clock className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="responseTime"
          chartType="line"
          customDbNames={Object.fromEntries(databases.map(db => [db, getDbDisplayName(db)]))}
          getDbType={getDbType}
        />
        <TimeSeriesChart
          title="TPS (транзакций/сек)"
          icon={<Gauge className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="tps"
          chartType="area"
          customDbNames={Object.fromEntries(databases.map(db => [db, getDbDisplayName(db)]))}
          getDbType={getDbType}
        />
        <TimeSeriesChart
          title="Активные соединения"
          icon={<Users className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="connections"
          chartType="line"
          customDbNames={Object.fromEntries(databases.map(db => [db, getDbDisplayName(db)]))}
          getDbType={getDbType}
        />
        <TimeSeriesChart
          title="Количество ошибок"
          icon={<AlertTriangle className="h-5 w-5 text-destructive" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="errors"
          chartType="line"
          customDbNames={Object.fromEntries(databases.map(db => [db, getDbDisplayName(db)]))}
          getDbType={getDbType}
        />
      </div>
    </div>
  )
}
