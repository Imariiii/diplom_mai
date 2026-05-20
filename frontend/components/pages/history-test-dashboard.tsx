"use client"

/**
 * Дашборд метрик для просмотра сохранённого прогона из истории:
 * та же структура вкладок и графиков, что на странице «Дашборды» после завершения теста.
 */

import { useEffect, useMemo, useState } from "react"
import { Database, Cpu, BarChart3, Lock } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiClient } from "@/lib/api"
import type { HistoryTestResult, HistoryTestRun } from "@/lib/api"
import { DB_NAMES } from "@/lib/chart-colors"
import { mapRawDbmsCacheFields } from "@/lib/dbms-cache-metrics"
import { getVisibleSelfCheckWarnings } from "@/lib/self-check"
import type { DBMSInternalMetrics, TestResult, TimeSeriesPoint } from "@/lib/types"
import {
  buildChartDataFromTimeSeries,
  CHART_TIMELINE_AXIS_TITLE,
  type ChartTimelineMode,
} from "@/lib/time-series-chart-data"
import {
  pickAggregateAttemptRate,
  pickAggregateThroughput,
  timeSeriesAttemptRate,
  timeSeriesSuccessfulThroughput,
} from "@/lib/throughput-metrics"
import { DatabaseMetricsTab } from "./dashboards/database-metrics-tab"
import { SystemMetricsTab } from "./dashboards/system-metrics-tab"
import { TransactionMetricsTab } from "./dashboards/transaction-metrics-tab"
import { DbmsMetricsTab } from "./dashboards/dbms-metrics-tab"

interface HistoryTsPoint {
  id: number
  test_run_id: string
  db_type: string
  connection_key?: string | null
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
}

type DashboardResult = {
  databaseId: string
  databaseType: string
  databaseName: string
  indexInfo?: Record<string, unknown>
  selfCheckWarnings: string[]
  metrics: {
    avgResponseTime: number
    p50ResponseTime: number
    p95ResponseTime: number
    p99ResponseTime: number
    minResponseTime: number
    maxResponseTime: number
    throughput: number
    attemptRate?: number
    activeConnections: number
    errorCount: number
    errorRate: number
  }
  dbmsMetrics?: {
    cacheHitRatio: number | null
    bufferPoolHitRatio: number | null
    cacheHitRatioStatus?: "ok" | "no_activity" | "invalid_counter" | "unavailable" | "error"
    cacheHitRatioNote?: string
    cacheHitRatioMode?: "delta" | string
    bufferSizeMB?: number
    bufferSizeLabel?: string
    lockWaits: number
    lockWaitsMode?: "current" | "delta" | "sampled_max"
    deadlocks: number
    deadlocksMode?: "current" | "delta" | "sampled_max"
    tableSizesMB: Record<string, number>
    indexSizesMB: Record<string, number>
    totalDBSizeMB: number
  }
  transactionMetrics: {
    totalTransactions: number
    successfulTransactions: number
    failedTransactions: number
    rollbacks: number
  }
  systemMetrics?: {
    cpuUsage: number
    memoryUsageMB: number
    memoryUsagePercent: number
    diskIOps: number
    diskReadMBps: number
    diskWriteMBps: number
    networkInMBps: number
    networkOutMBps: number
  }
}

function groupKeyFromHistoryRow(row: HistoryTestResult): string {
  const m = row.metrics || {}
  const key = (m.connection_key as string) || (m.db_name as string) || row.db_type
  return key || "unknown"
}

function mapSystemMetrics(raw: Record<string, number> | null | undefined): DashboardResult["systemMetrics"] {
  if (!raw) return undefined
  return {
    cpuUsage: raw.cpu_usage ?? 0,
    memoryUsageMB: raw.memory_usage_mb ?? 0,
    memoryUsagePercent: raw.memory_usage_percent ?? 0,
    diskIOps: raw.disk_iops ?? 0,
    diskReadMBps: raw.disk_read_mbps ?? 0,
    diskWriteMBps: raw.disk_write_mbps ?? 0,
    networkInMBps: raw.network_in_mbps ?? 0,
    networkOutMBps: raw.network_out_mbps ?? 0,
  }
}

function mapDbmsMetrics(raw: Record<string, unknown> | null | undefined): DashboardResult["dbmsMetrics"] {
  if (!raw) return undefined
  const cache = mapRawDbmsCacheFields(raw)
  return {
    cacheHitRatio: cache.cacheHitRatio,
    bufferPoolHitRatio: cache.bufferPoolHitRatio ?? cache.cacheHitRatio,
    cacheHitRatioStatus: (cache.cacheHitRatioStatus ?? undefined) as DBMSInternalMetrics["cacheHitRatioStatus"],
    cacheHitRatioNote: cache.cacheHitRatioNote ?? undefined,
    cacheHitRatioMode: (cache.cacheHitRatioMode ?? undefined) as DBMSInternalMetrics["cacheHitRatioMode"],
    bufferSizeMB: Number(raw.buffer_size_mb) || 0,
    bufferSizeLabel: typeof raw.buffer_size_label === "string" ? raw.buffer_size_label : undefined,
    lockWaits: Number(raw.lock_waits) || 0,
    lockWaitsMode: raw.lock_waits_mode as "current" | "delta" | "sampled_max" | undefined,
    deadlocks: Number(raw.deadlocks) || 0,
    deadlocksMode: raw.deadlocks_mode as "current" | "delta" | "sampled_max" | undefined,
    tableSizesMB: (raw.table_sizes_mb as Record<string, number>) || {},
    indexSizesMB: (raw.index_sizes_mb as Record<string, number>) || {},
    totalDBSizeMB: Number(raw.total_db_size_mb) || 0,
  }
}

function aggregateHistoryResults(results: HistoryTestResult[]): {
  formattedResults: DashboardResult[]
  connectionNames: Record<string, string>
  connectionDbTypes: Record<string, string>
} {
  type Bucket = {
    rollbacks: number
    workloadMode?: string
    avgTimes: number[]
    p50Times: number[]
    p95Times: number[]
    p99Times: number[]
    minTimes: number[]
    maxTimes: number[]
    throughputValues: number[]
    attemptRateValues: number[]
    activeConnections: number[]
    successful: number
    failed: number
    indexInfo?: Record<string, unknown>
    selfCheckWarnings: string[]
    system_metrics?: Record<string, number> | null
    dbms_metrics?: Record<string, unknown> | null
    dbType: string
    dbName: string
  }

  const aggregateByDb: Record<string, Bucket> = {}
  const connectionNames: Record<string, string> = {}
  const connectionDbTypes: Record<string, string> = {}

  for (const row of results) {
    const m = row.metrics || {}
    const dbKey = groupKeyFromHistoryRow(row)
    if (!aggregateByDb[dbKey]) {
      aggregateByDb[dbKey] = {
        rollbacks: 0,
        avgTimes: [],
        p50Times: [],
        p95Times: [],
        p99Times: [],
        minTimes: [],
        maxTimes: [],
        throughputValues: [],
        attemptRateValues: [],
        activeConnections: [],
        successful: 0,
        failed: 0,
        selfCheckWarnings: [],
        dbType: row.db_type,
        dbName: (m.db_name as string) || DB_NAMES[row.db_type] || row.db_type,
      }
    }
    const bucket = aggregateByDb[dbKey]
    if (typeof m.avg_time_ms === "number") bucket.avgTimes.push(m.avg_time_ms)
    if (typeof m.p50_time_ms === "number") bucket.p50Times.push(m.p50_time_ms)
    if (typeof m.p95_time_ms === "number") bucket.p95Times.push(m.p95_time_ms)
    if (typeof m.p99_time_ms === "number") bucket.p99Times.push(m.p99_time_ms)
    if (typeof m.min_time_ms === "number") bucket.minTimes.push(m.min_time_ms)
    if (typeof m.max_time_ms === "number") bucket.maxTimes.push(m.max_time_ms)
    const tp = pickAggregateThroughput(m)
    if (tp !== undefined) bucket.throughputValues.push(tp)
    const ar = pickAggregateAttemptRate(m)
    if (ar !== undefined) bucket.attemptRateValues.push(ar)
    if (typeof m.active_connections === "number") bucket.activeConnections.push(m.active_connections)
    bucket.successful += m.successful_transactions ?? m.successful ?? 0
    bucket.failed += m.failed_transactions ?? m.failed ?? 0
    bucket.rollbacks += Number(m.rollbacks) || 0
    if (m.workload_mode) bucket.workloadMode = String(m.workload_mode)
    if (m.index_info) bucket.indexInfo = m.index_info as Record<string, unknown>
    getVisibleSelfCheckWarnings(m.self_check).forEach((warning) => {
      if (!bucket.selfCheckWarnings.includes(warning)) {
        bucket.selfCheckWarnings.push(warning)
      }
    })
    if (row.system_metrics && !bucket.system_metrics) {
      bucket.system_metrics = row.system_metrics
    }
    if (row.dbms_metrics) {
      bucket.dbms_metrics = row.dbms_metrics as Record<string, unknown>
    }
    const dtype = (m.dbms_type as string) || row.db_type
    bucket.dbType = dtype
    bucket.dbName = (m.db_name as string) || bucket.dbName
    connectionNames[dbKey] = (m.db_name as string) || connectionNames[dbKey] || DB_NAMES[dtype] || dbKey
    connectionDbTypes[dbKey] = dtype
  }

  const average = (values: number[]) =>
    values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

  const formattedResults: DashboardResult[] = Object.entries(aggregateByDb).map(([dbKey, bucket]) => {
    const totalTransactions = bucket.successful + bucket.failed
    return {
      databaseId: dbKey,
      databaseType: bucket.dbType,
      databaseName: connectionNames[dbKey] || bucket.dbName,
      indexInfo: bucket.indexInfo,
      selfCheckWarnings: bucket.selfCheckWarnings,
      metrics: {
        avgResponseTime: average(bucket.avgTimes),
        p50ResponseTime: average(bucket.p50Times),
        p95ResponseTime: average(bucket.p95Times),
        p99ResponseTime: average(bucket.p99Times),
        minResponseTime: bucket.minTimes.length ? Math.min(...bucket.minTimes) : 0,
        maxResponseTime: bucket.maxTimes.length ? Math.max(...bucket.maxTimes) : 0,
        throughput: average(bucket.throughputValues),
        attemptRate: bucket.attemptRateValues.length
          ? average(bucket.attemptRateValues)
          : undefined,
        activeConnections: bucket.activeConnections.length
          ? Math.round(average(bucket.activeConnections))
          : 0,
        errorCount: bucket.failed,
        errorRate: totalTransactions > 0 ? (bucket.failed / totalTransactions) * 100 : 0,
      },
      dbmsMetrics: mapDbmsMetrics(bucket.dbms_metrics),
      transactionMetrics: {
        totalTransactions,
        successfulTransactions: bucket.successful,
        failedTransactions: bucket.failed,
        rollbacks: bucket.rollbacks,
      },
      systemMetrics: mapSystemMetrics(bucket.system_metrics),
    }
  })

  return { formattedResults, connectionNames, connectionDbTypes }
}

function rawHistoryPointToTimeSeries(p: HistoryTsPoint): TimeSeriesPoint {
  return {
    timestamp: new Date(p.timestamp).getTime(),
    responseTime: p.response_time ?? 0,
    attemptRate: timeSeriesAttemptRate(p),
    throughput: timeSeriesSuccessfulThroughput(p),
    activeConnections: p.active_connections ?? 0,
    errorCount: p.error_count ?? 0,
    cpuUsage: p.cpu_usage ?? 0,
    memoryUsage: p.memory_usage ?? 0,
    memoryUsageMB: p.memory_usage_mb ?? 0,
    diskIOps: p.disk_iops ?? 0,
    networkIn: p.network_in ?? 0,
    networkOut: p.network_out ?? 0,
    cacheHitRatio: 0,
    bufferPoolHitRatio: 0,
    lockWaits: 0,
    deadlocks: 0,
  }
}

function buildRealtimeByConnection(
  formattedResults: DashboardResult[],
  points: HistoryTsPoint[],
): Record<string, TimeSeriesPoint[]> {
  const byKey: Record<string, HistoryTsPoint[]> = {}
  for (const p of points) {
    const key = p.connection_key || p.db_type
    if (!byKey[key]) byKey[key] = []
    byKey[key].push(p)
  }
  for (const key of Object.keys(byKey)) {
    byKey[key].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  }

  const out: Record<string, TimeSeriesPoint[]> = {}
  for (const r of formattedResults) {
    const series = byKey[r.databaseId] || byKey[r.databaseType] || []
    out[r.databaseId] = series.map(rawHistoryPointToTimeSeries)
  }
  return out
}

export function HistoryTestDashboard({
  test,
  virtualUsers,
}: {
  test: HistoryTestRun & { results: HistoryTestResult[] }
  virtualUsers: number
}) {
  const [tsPoints, setTsPoints] = useState<HistoryTsPoint[]>([])
  const [chartTimelineMode, setChartTimelineMode] = useState<ChartTimelineMode>("timeline")

  const { formattedResults, connectionNames, connectionDbTypes } = useMemo(
    () => aggregateHistoryResults(test.results || []),
    [test.results],
  )

  useEffect(() => {
    let cancelled = false
    apiClient
      .getHistoryTestTimeSeries(test.id, { full: true })
      .then((res) => {
        if (!cancelled) {
          setTsPoints((res.points || []) as HistoryTsPoint[])
        }
      })
      .catch(() => {
        if (!cancelled) setTsPoints([])
      })

    return () => {
      cancelled = true
    }
  }, [test.id])

  const realtimeData = useMemo(
    () => buildRealtimeByConnection(formattedResults, tsPoints),
    [formattedResults, tsPoints],
  )

  const chartData = useMemo(
    () => buildChartDataFromTimeSeries(realtimeData, { mode: chartTimelineMode }),
    [realtimeData, chartTimelineMode],
  )
  const chartXAxisTitle = CHART_TIMELINE_AXIS_TITLE[chartTimelineMode]
  const workloadMode = test.summary?.workload_mode || test.config?.workload_mode
  const primaryRateUnit = test.summary?.primary_rate_unit || test.config?.primary_rate_unit

  const chartDatabases = useMemo(() => {
    if (Object.keys(realtimeData).length > 0) {
      return Object.keys(realtimeData)
    }
    return formattedResults.map((r) => r.databaseId)
  }, [realtimeData, formattedResults])

  const isTestFinished = test.status === "completed" || test.status === "failed"
  const hasCompletedResults =
    test.status === "completed" && formattedResults.length > 0

  const getDbDisplayName = (dbId: string) =>
    connectionNames[dbId] || formattedResults.find((r) => r.databaseId === dbId)?.databaseName || DB_NAMES[dbId] || dbId

  const getDbType = (dbKey: string): string =>
    connectionDbTypes[dbKey] || formattedResults.find((r) => r.databaseId === dbKey)?.databaseType || dbKey

  const findResultByDbKey = (dbKey: string) => {
    const r = formattedResults.find((item) => item.databaseId === dbKey)
    if (!r) return undefined
    return {
      databaseId: r.databaseId,
      indexInfo: r.indexInfo as { enabled?: boolean; indexes_count?: number; total_creation_time_ms?: number; drop_time_ms?: number } | undefined,
      selfCheckWarnings: r.selfCheckWarnings,
      metrics: {
        avgResponseTime: r.metrics.avgResponseTime,
        p50ResponseTime: r.metrics.p50ResponseTime,
        p95ResponseTime: r.metrics.p95ResponseTime,
        p99ResponseTime: r.metrics.p99ResponseTime,
        minResponseTime: r.metrics.minResponseTime,
        maxResponseTime: r.metrics.maxResponseTime,
        throughput: r.metrics.throughput,
        attemptRate: r.metrics.attemptRate,
        activeConnections: r.metrics.activeConnections,
        errorCount: r.metrics.errorCount,
        errorRate: r.metrics.errorRate,
      },
      dbmsMetrics: r.dbmsMetrics,
      transactionMetrics: r.transactionMetrics,
      systemMetrics: r.systemMetrics,
      timeSeriesData: [] as TimeSeriesPoint[],
    }
  }

  const getLatestMetric = (dbId: string, metric: string) => {
    const points = realtimeData[dbId]
    if (!points || points.length === 0) return "—"
    const value = points[points.length - 1][metric as keyof TimeSeriesPoint]
    return typeof value === "number" ? value.toFixed(2) : "—"
  }

  const dashboardResultsForTabs = useMemo(
    (): TestResult[] =>
      formattedResults.map((r) => ({
        databaseId: r.databaseId,
        databaseType: r.databaseType,
        databaseName: r.databaseName,
        indexInfo: r.indexInfo as TestResult["indexInfo"],
        selfCheckWarnings: r.selfCheckWarnings,
        metrics: r.metrics,
        dbmsMetrics: r.dbmsMetrics,
        transactionMetrics: r.transactionMetrics,
        systemMetrics: r.systemMetrics,
        timeSeriesData: [],
      })),
    [formattedResults],
  )

  if (!hasCompletedResults) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-4 py-12 text-center text-sm text-muted-foreground">
        Нет агрегированных метрик для дашборда (тест не завершён или результаты отсутствуют).
      </div>
    )
  }

  return (
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
          virtualUsers={virtualUsers}
          isTestFinished={isTestFinished}
          showCharts={isTestFinished}
          chartXAxisTitle={chartXAxisTitle}
          chartTimelineMode={chartTimelineMode}
          onChartTimelineModeChange={setChartTimelineMode}
          workloadMode={workloadMode}
          primaryRateUnit={primaryRateUnit}
        />
      </TabsContent>

      {isTestFinished && (
        <TabsContent value="system">
          <SystemMetricsTab
            databases={chartDatabases}
            chartData={chartData}
            getDbType={getDbType}
            getDbDisplayName={getDbDisplayName}
            chartXAxisTitle={chartXAxisTitle}
            chartTimelineMode={chartTimelineMode}
            onChartTimelineModeChange={setChartTimelineMode}
          />
        </TabsContent>
      )}

      {isTestFinished && (
        <TabsContent value="transactions">
          <TransactionMetricsTab
            databases={chartDatabases}
            results={dashboardResultsForTabs}
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
  )
}
