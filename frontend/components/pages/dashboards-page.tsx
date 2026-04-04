"use client"

import { useEffect, useState } from "react"
import { Database, Cpu, BarChart3, Lock } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAppStore } from "@/lib/store"
import { useTestWebSocket } from "@/hooks/use-test-websocket"
import { apiClient } from "@/lib/api"
import { toast } from "sonner"
import { DB_NAMES } from "@/lib/chart-colors"
import { EmptyStateCard } from "./dashboards/empty-state-card"
import { PageHeader } from "./dashboards/page-header"
import { TestProgressBar } from "./dashboards/test-progress-bar"
import { DatabaseMetricsTab } from "./dashboards/database-metrics-tab"
import { SystemMetricsTab } from "./dashboards/system-metrics-tab"
import { TransactionMetricsTab } from "./dashboards/transaction-metrics-tab"
import { DbmsMetricsTab } from "./dashboards/dbms-metrics-tab"

export function DashboardsPage() {
  const { currentTest, realtimeData, testConfig, setCurrentTest, addTestToHistory, clearRealtimeData } = useAppStore()
  const [statusMessage, setStatusMessage] = useState<string>("")

  const {
    isConnected,
    progress,
    status,
    elapsedSeconds,
    remainingSeconds,
  } = useTestWebSocket({
    testId: currentTest?.id || "",
    onStatus: (data) => {
      setStatusMessage(data.message || "")

      if (data.status === "completed" || data.status === "failed") {
        if (currentTest) {
          const updatedTest = {
            ...currentTest,
            status: data.status,
            endTime: new Date(),
          }

          if (data.status === "completed") {
            apiClient.getAsyncTestResults(currentTest.id).then((response) => {
              if (response.results) {
                const aggregateByDb: Record<string, {
                  avgTimes: number[]
                  p50Times: number[]
                  p95Times: number[]
                  p99Times: number[]
                  minTimes: number[]
                  maxTimes: number[]
                  tpsValues: number[]
                  throughputValues: number[]
                  activeConnections: number[]
                  successful: number
                  failed: number
                }> = {}

                response.results.forEach((result: any) => {
                  const comparison = result.comparison || {}
                  const entries = Object.entries(comparison)

                  if (entries.length > 0) {
                    entries.forEach(([dbType, stats]: [string, any]) => {
                      if (!aggregateByDb[dbType]) {
                        aggregateByDb[dbType] = {
                          avgTimes: [], p50Times: [], p95Times: [], p99Times: [],
                          minTimes: [], maxTimes: [], tpsValues: [], throughputValues: [],
                          activeConnections: [], successful: 0, failed: 0,
                        }
                      }
                      const bucket = aggregateByDb[dbType]
                      if (typeof stats.avg_time_ms === "number") bucket.avgTimes.push(stats.avg_time_ms)
                      if (typeof stats.p50_time_ms === "number") bucket.p50Times.push(stats.p50_time_ms)
                      if (typeof stats.p95_time_ms === "number") bucket.p95Times.push(stats.p95_time_ms)
                      if (typeof stats.p99_time_ms === "number") bucket.p99Times.push(stats.p99_time_ms)
                      if (typeof stats.min_time_ms === "number") bucket.minTimes.push(stats.min_time_ms)
                      if (typeof stats.max_time_ms === "number") bucket.maxTimes.push(stats.max_time_ms)
                      if (typeof stats.tps === "number") bucket.tpsValues.push(stats.tps)
                      if (typeof stats.throughput === "number") bucket.throughputValues.push(stats.throughput)
                      if (typeof stats.active_connections === "number") bucket.activeConnections.push(stats.active_connections)
                      bucket.successful += stats.successful || 0
                      bucket.failed += stats.failed || 0
                    })
                  } else if (result.db_type && result.stats) {
                    const dbType = result.db_type
                    const stats = result.stats
                    if (!aggregateByDb[dbType]) {
                      aggregateByDb[dbType] = {
                        avgTimes: [], p50Times: [], p95Times: [], p99Times: [],
                        minTimes: [], maxTimes: [], tpsValues: [], throughputValues: [],
                        activeConnections: [], successful: 0, failed: 0,
                      }
                    }
                    const bucket = aggregateByDb[dbType]
                    if (typeof stats.avg_time_ms === "number") bucket.avgTimes.push(stats.avg_time_ms)
                    if (typeof stats.p50_time_ms === "number") bucket.p50Times.push(stats.p50_time_ms)
                    if (typeof stats.p95_time_ms === "number") bucket.p95Times.push(stats.p95_time_ms)
                    if (typeof stats.p99_time_ms === "number") bucket.p99Times.push(stats.p99_time_ms)
                    if (typeof stats.min_time_ms === "number") bucket.minTimes.push(stats.min_time_ms)
                    if (typeof stats.max_time_ms === "number") bucket.maxTimes.push(stats.max_time_ms)
                    if (typeof stats.tps === "number") bucket.tpsValues.push(stats.tps)
                    if (typeof stats.throughput === "number") bucket.throughputValues.push(stats.throughput)
                    if (typeof stats.active_connections === "number") bucket.activeConnections.push(stats.active_connections)
                    bucket.successful += stats.successful || 0
                    bucket.failed += stats.failed || 0
                  }
                })

                const average = (values: number[]) =>
                  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

                const formattedResults = Object.entries(aggregateByDb).map(([dbType, bucket]) => {
                  const totalTransactions = bucket.successful + bucket.failed
                  const dbmsMetricsData = response.dbms_metrics?.[dbType]

                  return {
                    databaseId: dbType,
                    databaseName: DB_NAMES[dbType] || dbType,
                    metrics: {
                      avgResponseTime: average(bucket.avgTimes),
                      p50ResponseTime: average(bucket.p50Times),
                      p95ResponseTime: average(bucket.p95Times),
                      p99ResponseTime: average(bucket.p99Times),
                      minResponseTime: bucket.minTimes.length ? Math.min(...bucket.minTimes) : 0,
                      maxResponseTime: bucket.maxTimes.length ? Math.max(...bucket.maxTimes) : 0,
                      tps: average(bucket.tpsValues),
                      throughput: average(bucket.throughputValues),
                      activeConnections: bucket.activeConnections.length
                        ? Math.round(average(bucket.activeConnections))
                        : testConfig.virtualUsers,
                      errorCount: bucket.failed,
                      errorRate: totalTransactions > 0 ? (bucket.failed / totalTransactions) * 100 : 0,
                    },
                    dbmsMetrics: dbmsMetricsData ? {
                      cacheHitRatio: dbmsMetricsData.cache_hit_ratio || 0,
                      bufferPoolHitRatio: dbmsMetricsData.buffer_pool_hit_ratio || 0,
                      lockWaits: dbmsMetricsData.lock_waits || 0,
                      deadlocks: dbmsMetricsData.deadlocks || 0,
                      tableSizesMB: dbmsMetricsData.table_sizes_mb || {},
                      indexSizesMB: dbmsMetricsData.index_sizes_mb || {},
                      totalDBSizeMB: dbmsMetricsData.total_db_size_mb || 0,
                    } : undefined,
                    transactionMetrics: {
                      totalTransactions,
                      successfulTransactions: bucket.successful,
                      failedTransactions: bucket.failed,
                      rollbacks: 0,
                    },
                    systemMetrics: response.system_metrics?.[dbType],
                    timeSeriesData: [],
                  }
                })

                setCurrentTest({
                  ...updatedTest,
                  summary: response.summary,
                  results: formattedResults,
                })
                addTestToHistory({
                  ...updatedTest,
                  summary: response.summary,
                  results: formattedResults,
                })
                toast.success("Тестирование завершено!")
              }
            }).catch(console.error)
          } else {
            setCurrentTest(updatedTest)
            toast.error("Тестирование завершилось с ошибкой")
          }
        }
      }
    },
    onConnect: () => {
      toast.success("Подключено к real-time обновлениям")
    },
    onDisconnect: () => {
      if (currentTest?.status === "running") {
        toast.warning("Соединение потеряно, переподключение...")
      }
    },
  })

  useEffect(() => {
    return () => {
      if (currentTest?.status !== "completed") {
        clearRealtimeData()
      }
    }
  }, [currentTest?.id])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const chartData = Object.entries(realtimeData).reduce<Record<string, unknown>[]>((acc, [dbId, points]) => {
    points.forEach((point, index) => {
      if (!acc[index]) {
        acc[index] = { time: new Date(point.timestamp).toLocaleTimeString("ru") }
      }
      acc[index][`${dbId}_responseTime`] = point.responseTime?.toFixed(2) || 0
      acc[index][`${dbId}_throughput`] = point.throughput?.toFixed(0) || 0
      acc[index][`${dbId}_tps`] = point.tps?.toFixed(0) || 0
      acc[index][`${dbId}_cpu`] = point.cpuUsage?.toFixed(1) || 0
      acc[index][`${dbId}_memory`] = point.memoryUsage?.toFixed(1) || 0
      acc[index][`${dbId}_diskIO`] = point.diskIOps?.toFixed(0) || 0
      acc[index][`${dbId}_connections`] = point.activeConnections || 0
      acc[index][`${dbId}_errors`] = point.errorCount || 0
    })
    return acc
  }, [])

  const getLatestMetric = (dbId: string, metric: string) => {
    const points = realtimeData[dbId]
    if (!points || points.length === 0) return "—"
    const value = points[points.length - 1][metric as keyof typeof points[number]]
    return typeof value === "number" ? value.toFixed(2) : value
  }

  const getResultForDb = (dbId: string) => {
    return currentTest?.results?.find(r => r.databaseId === dbId)
  }

  if (!currentTest && Object.keys(realtimeData).length === 0) {
    return <EmptyStateCard />
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader isConnected={isConnected} currentTest={currentTest} />

      {currentTest?.status === "running" && (
        <TestProgressBar
          progress={progress}
          elapsedSeconds={elapsedSeconds}
          statusMessage={statusMessage}
          formatTime={formatTime}
        />
      )}

      <Tabs defaultValue="database" className="space-y-4">
        <TabsList className="bg-muted">
          <TabsTrigger value="database" className="text-foreground data-[state=active]:text-foreground">
            <Database className="h-4 w-4 mr-2" />
            База данных
          </TabsTrigger>
          <TabsTrigger value="system" className="text-foreground data-[state=active]:text-foreground">
            <Cpu className="h-4 w-4 mr-2" />
            Системные
          </TabsTrigger>
          <TabsTrigger value="transactions" className="text-foreground data-[state=active]:text-foreground">
            <BarChart3 className="h-4 w-4 mr-2" />
            Транзакции
          </TabsTrigger>
          <TabsTrigger value="dbms" className="text-foreground data-[state=active]:text-foreground">
            <Lock className="h-4 w-4 mr-2" />
            Внутренние СУБД
          </TabsTrigger>
        </TabsList>

        <TabsContent value="database">
          <DatabaseMetricsTab
            databases={testConfig.databases}
            chartData={chartData}
            getResultForDb={getResultForDb}
            getLatestMetric={getLatestMetric}
            virtualUsers={testConfig.virtualUsers}
          />
        </TabsContent>

        <TabsContent value="system">
          <SystemMetricsTab
            databases={testConfig.databases}
            chartData={chartData}
          />
        </TabsContent>

        <TabsContent value="transactions">
          <TransactionMetricsTab
            databases={testConfig.databases}
            results={currentTest?.results}
          />
        </TabsContent>

        <TabsContent value="dbms">
          <DbmsMetricsTab
            databases={testConfig.databases}
            realtimeData={realtimeData}
            getResultForDb={getResultForDb}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
