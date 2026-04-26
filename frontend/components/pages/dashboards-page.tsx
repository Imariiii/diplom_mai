"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Database, Cpu, BarChart3, Lock, AlertTriangle, CheckCircle2, History, SlidersHorizontal, Loader2 } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
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
  const { currentTest, realtimeData, testConfig, setCurrentTest, addTestToHistory, clearRealtimeData, connectionNames, setConnectionNames, connectionDbTypes, setConnectionDbTypes, setCurrentPage, setComparisonSelection } = useAppStore()
  const [statusMessage, setStatusMessage] = useState<string>("")
  const [showProgressBar, setShowProgressBar] = useState(false)

  // Ref always holds the latest currentTest so the cleanup closure is never stale.
  const currentTestRef = useRef(currentTest)
  currentTestRef.current = currentTest

  const {
    isConnected,
    progress,
    status,
    backupStatus,
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
              if (response.connection_names) {
                setConnectionNames(response.connection_names)
              }
              if (response.connection_db_types) {
                setConnectionDbTypes(response.connection_db_types)
              }
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
                  indexInfo?: any
                  selfCheckWarnings: string[]
                }> = {}

                response.results.forEach((result: any) => {
                  const comparison = result.comparison || {}
                  const entries = Object.entries(comparison)

                  if (entries.length > 0) {
                    entries.forEach(([dbKey, stats]: [string, any]) => {
                      if (!aggregateByDb[dbKey]) {
                        aggregateByDb[dbKey] = {
                          avgTimes: [], p50Times: [], p95Times: [], p99Times: [],
                          minTimes: [], maxTimes: [], tpsValues: [], throughputValues: [],
                          activeConnections: [], successful: 0, failed: 0, selfCheckWarnings: [],
                        }
                      }
                      const bucket = aggregateByDb[dbKey]
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
                      if (stats.index_info) bucket.indexInfo = stats.index_info
                      if (Array.isArray(stats.self_check?.warnings)) {
                        stats.self_check.warnings.forEach((warning: unknown) => {
                          if (typeof warning === "string" && !bucket.selfCheckWarnings.includes(warning)) {
                            bucket.selfCheckWarnings.push(warning)
                          }
                        })
                      }
                    })
                  } else if (result.db_key && result.stats) {
                    const dbKey = result.db_key
                    const stats = result.stats
                    if (!aggregateByDb[dbKey]) {
                      aggregateByDb[dbKey] = {
                        avgTimes: [], p50Times: [], p95Times: [], p99Times: [],
                        minTimes: [], maxTimes: [], tpsValues: [], throughputValues: [],
                          activeConnections: [], successful: 0, failed: 0, selfCheckWarnings: [],
                      }
                    }
                    const bucket = aggregateByDb[dbKey]
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
                    if (stats.index_info) bucket.indexInfo = stats.index_info
                    if (Array.isArray(stats.self_check?.warnings)) {
                      stats.self_check.warnings.forEach((warning: unknown) => {
                        if (typeof warning === "string" && !bucket.selfCheckWarnings.includes(warning)) {
                          bucket.selfCheckWarnings.push(warning)
                        }
                      })
                    }
                  }
                })

                const average = (values: number[]) =>
                  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

                const formattedResults = Object.entries(aggregateByDb).map(([dbKey, bucket]) => {
                  const totalTransactions = bucket.successful + bucket.failed
                  const dbmsMetricsData = response.dbms_metrics?.[dbKey]
                  const connName = response.connection_names?.[dbKey]
                  const dbType = response.connection_db_types?.[dbKey] || dbKey

                  return {
                    databaseId: dbKey,
                    databaseType: dbType,
                    databaseName: connName || DB_NAMES[dbType] || dbType,
                    indexInfo: bucket.indexInfo,
                    selfCheckWarnings: bucket.selfCheckWarnings,
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
                      lockWaitsMode: dbmsMetricsData.lock_waits_mode,
                      deadlocks: dbmsMetricsData.deadlocks || 0,
                      deadlocksMode: dbmsMetricsData.deadlocks_mode,
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
                    systemMetrics: response.system_metrics?.[dbKey],
                    timeSeriesData: [],
                  }
                })

                setCurrentTest({
                  ...updatedTest,
                  summary: response.summary,
                  results: formattedResults,
                  connection_names: response.connection_names,
                  connection_db_types: response.connection_db_types,
                })
                addTestToHistory({
                  ...updatedTest,
                  summary: response.summary,
                  results: formattedResults,
                  connection_names: response.connection_names,
                  connection_db_types: response.connection_db_types,
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
      if (currentTestRef.current?.status !== "completed") {
        clearRealtimeData()
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTest?.id])

  // Показываем прогресс-бар во время теста и ещё 2 секунды после завершения,
  // чтобы пользователь успел увидеть финальные 100%
  useEffect(() => {
    if (status === "running") {
      setShowProgressBar(true)
    } else if (status === "completed" || status === "failed") {
      const t = setTimeout(() => setShowProgressBar(false), 2000)
      return () => clearTimeout(t)
    }
  }, [status])

  const getDbDisplayName = (dbId: string) => {
    return currentTest?.connection_names?.[dbId] || connectionNames[dbId] || DB_NAMES[dbId] || dbId
  }

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
      acc[index][`${dbId}_responseTime`] = point.responseTime ?? 0
      acc[index][`${dbId}_throughput`] = point.throughput ?? 0
      acc[index][`${dbId}_tps`] = point.tps ?? 0
      acc[index][`${dbId}_cpu`] = point.cpuUsage ?? 0
      acc[index][`${dbId}_memory`] = point.memoryUsage ?? 0
      acc[index][`${dbId}_diskIO`] = point.diskIOps ?? 0
      acc[index][`${dbId}_connections`] = point.activeConnections ?? 0
      acc[index][`${dbId}_errors`] = point.errorCount ?? 0
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

  const getDbType = (dbKey: string): string => {
    const result = currentTest?.results?.find((item) => item.databaseId === dbKey)
    if (result?.databaseType) {
      return result.databaseType
    }

    if (connectionDbTypes[dbKey]) {
      return connectionDbTypes[dbKey]
    }

    if (currentTest?.connection_db_types?.[dbKey]) {
      return currentTest.connection_db_types[dbKey]
    }

    return dbKey
  }

  // Функция для поиска результата по ключу из realtimeData
  const findResultByDbKey = (dbKey: string) => {
    return currentTest?.results?.find(r => r.databaseId === dbKey)
  }

  const chartDatabases = Object.keys(realtimeData).length > 0
    ? Object.keys(realtimeData)
    : (currentTest?.results?.map((result) =>
        currentTest.connection_names?.[result.databaseId]
          || connectionNames[result.databaseId]
          || result.databaseId
      ) || [])

  const isTestFinished = currentTest?.status === "completed" || currentTest?.status === "failed"
  const hasCompletedResults =
    currentTest?.status === "completed" &&
    Array.isArray(currentTest.results) &&
    currentTest.results.length > 0
  const showFinalizingBanner =
    (currentTest?.status === "completed" && !hasCompletedResults) ||
    (currentTest?.status === "running" && statusMessage.includes("Финализация"))
  const selfCheckResults = useMemo(
    () => currentTest?.results?.filter((result) => (result.selfCheckWarnings?.length || 0) > 0) || [],
    [currentTest?.results]
  )

  if (!currentTest && Object.keys(realtimeData).length === 0) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] w-full min-w-0 max-w-full flex-col p-6">
        <PageHeader isConnected={isConnected} currentTest={null} />
        <div className="flex flex-1 flex-col items-center justify-center py-10 sm:py-16">
          <EmptyStateCard />
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader isConnected={isConnected} currentTest={currentTest} />

      {showProgressBar && (
        <TestProgressBar
          progress={Math.min(100, progress)}
          elapsedSeconds={elapsedSeconds}
          statusMessage={statusMessage}
          backupStatus={backupStatus}
          formatTime={formatTime}
        />
      )}

      {showFinalizingBanner && (
        <Alert className="border-border bg-muted/40">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          <AlertTitle>Финализация результатов</AlertTitle>
          <AlertDescription className="text-sm text-muted-foreground">
            Сбор метрик, сохранение в историю и подготовка сводки… Это обычно занимает несколько секунд.
          </AlertDescription>
        </Alert>
      )}

      {hasCompletedResults && (
        <div className="rounded-xl border border-success/30 bg-success/5 p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-success/15 text-success">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <p className="font-semibold text-foreground">Тест завершён успешно</p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Результаты сохранены в истории.
                  {elapsedSeconds > 0 && (
                    <> Время выполнения: <span className="font-mono">{formatTime(elapsedSeconds)}</span>.</>
                  )}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2 sm:flex-nowrap">
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => setCurrentPage("history")}
              >
                <History className="h-4 w-4" />
                История тестов
              </Button>
              <Button
                size="sm"
                className="gap-2"
                onClick={() => {
                  if (currentTest?.id) {
                    setComparisonSelection([currentTest.id], null, "per_test")
                    setCurrentPage("comparison")
                  }
                }}
              >
                <SlidersHorizontal className="h-4 w-4" />
                Сводка по прогону
              </Button>
            </div>
          </div>
        </div>
      )}

      {isTestFinished && selfCheckResults.length > 0 && (
        <Alert className="border-amber-500/30 bg-amber-500/5">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <AlertTitle>Предупреждения самопроверки</AlertTitle>
          <AlertDescription className="space-y-3">
            <p className="text-sm text-muted-foreground">
              После завершения теста система обнаружила потенциально неконсистентные метрики.
            </p>
            <div className="space-y-3">
              {selfCheckResults.map((result) => (
                <div key={result.databaseId} className="rounded-md border border-amber-500/20 bg-background/60 p-3">
                  <p className="text-sm font-medium">{result.databaseName}</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                    {result.selfCheckWarnings?.map((warning) => (
                      <li key={`${result.databaseId}-${warning}`}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="database" className="space-y-4">
        <TabsList className="bg-muted">
          <TabsTrigger value="database" className="text-foreground data-[state=active]:text-foreground">
            <Database className="h-4 w-4 mr-2" />
            База данных
          </TabsTrigger>
          {isTestFinished && (
            <TabsTrigger value="system" className="text-foreground data-[state=active]:text-foreground">
              <Cpu className="h-4 w-4 mr-2" />
              Системные
            </TabsTrigger>
          )}
          {isTestFinished && (
            <TabsTrigger value="transactions" className="text-foreground data-[state=active]:text-foreground">
              <BarChart3 className="h-4 w-4 mr-2" />
              Транзакции
            </TabsTrigger>
          )}
          <TabsTrigger value="dbms" className="text-foreground data-[state=active]:text-foreground">
            <Lock className="h-4 w-4 mr-2" />
            Внутренние СУБД
          </TabsTrigger>
        </TabsList>

        <TabsContent value="database">
          <DatabaseMetricsTab
            databases={chartDatabases}
            chartData={chartData}
            getResultForDb={findResultByDbKey}
            getLatestMetric={getLatestMetric}
            getDbDisplayName={getDbDisplayName}
            getDbType={getDbType}
            virtualUsers={testConfig.virtualUsers}
            showCharts={isTestFinished}
          />
        </TabsContent>

        {isTestFinished && (
          <TabsContent value="system">
            <SystemMetricsTab
              databases={chartDatabases}
              chartData={chartData}
              getDbType={getDbType}
              getDbDisplayName={getDbDisplayName}
            />
          </TabsContent>
        )}

        {isTestFinished && (
          <TabsContent value="transactions">
            <TransactionMetricsTab
              databases={chartDatabases}
              results={currentTest?.results}
              getDbType={getDbType}
              getDbDisplayName={getDbDisplayName}
            />
          </TabsContent>
        )}

        <TabsContent value="dbms">
          <DbmsMetricsTab
            databases={chartDatabases}
            realtimeData={realtimeData}
            getResultForDb={findResultByDbKey}
            getDbType={getDbType}
            getDbDisplayName={getDbDisplayName}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
