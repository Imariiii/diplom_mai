"use client"

import { useEffect, useMemo, useState } from "react"
import { Loader2, Activity, Clock, Gauge, Cpu, Users, AlertTriangle, MemoryStick } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { apiClient } from "@/lib/api"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { TimeSeriesChart } from "./dashboards/shared/time-series-chart"

interface RawPoint {
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
}

function buildChartData(points: RawPoint[]): {
  chartData: Record<string, unknown>[]
  databases: string[]
} {
  const grouped: Record<string, RawPoint[]> = {}
  for (const point of points) {
    if (!grouped[point.db_type]) grouped[point.db_type] = []
    grouped[point.db_type].push(point)
  }

  const databases = Object.keys(grouped)
  if (databases.length === 0) return { chartData: [], databases: [] }

  const maxLen = Math.max(...databases.map((db) => grouped[db].length))

  const chartData = Array.from({ length: maxLen }, (_, i) => {
    const row: Record<string, unknown> = {}
    const firstDb = databases[0]
    const anchor = grouped[firstDb]?.[i]
    row.time = anchor
      ? new Date(anchor.timestamp).toLocaleTimeString("ru")
      : String(i)

    for (const db of databases) {
      const pt = grouped[db]?.[i]
      if (pt) {
        row[`${db}_responseTime`] = pt.response_time ?? 0
        row[`${db}_tps`] = pt.tps ?? 0
        row[`${db}_cpu`] = pt.cpu_usage ?? 0
        row[`${db}_memory`] = pt.memory_usage ?? 0
        row[`${db}_connections`] = pt.active_connections ?? 0
        row[`${db}_errors`] = pt.error_count ?? 0
        row[`${db}_diskIO`] = pt.disk_iops ?? 0
      }
    }
    return row
  })

  return { chartData, databases }
}

function hasMetric(chartData: Record<string, unknown>[], databases: string[], key: string): boolean {
  return databases.some((db) =>
    chartData.some((row) => typeof row[`${db}_${key}`] === "number" && (row[`${db}_${key}` as string] as number) > 0)
  )
}

export function HistoryTimeSeriesTab({ testId }: { testId: string }) {
  const [points, setPoints] = useState<RawPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    apiClient
      .getHistoryTestTimeSeries(testId, { limit: 500 })
      .then((res) => {
        if (!cancelled) {
          setPoints(res.points || [])
          setLoaded(true)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Ошибка загрузки данных")
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [testId])

  const { chartData, databases } = useMemo(() => buildChartData(points), [points])

  const getDbDisplayName = (dbId: string) => DB_NAMES[dbId] || dbId
  const resolveDbColor = (dbId: string) => getDbColor(dbId)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Загрузка данных мониторинга…</span>
      </div>
    )
  }

  if (error) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="flex items-center justify-center py-10">
          <p className="text-destructive text-sm">{error}</p>
        </CardContent>
      </Card>
    )
  }

  if (loaded && points.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          <Activity className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-muted-foreground text-sm">
            Данные мониторинга для этого теста недоступны.
          </p>
          <p className="text-muted-foreground/60 text-xs text-center max-w-xs">
            Временные ряды сохраняются только для тестов, запущенных после включения истории.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (!loaded) return null

  const showCpu = hasMetric(chartData, databases, "cpu")
  const showMemory = hasMetric(chartData, databases, "memory")
  const showDiskIO = hasMetric(chartData, databases, "diskIO")

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {databases.map((db) => {
          const pts = points.filter((p) => p.db_type === db)
          const avg = (arr: (number | null)[]): number => {
            const valid = arr.filter((v): v is number => v !== null && v > 0)
            return valid.length ? valid.reduce((s, v) => s + v, 0) / valid.length : 0
          }
          const avgRt = avg(pts.map((p) => p.response_time))
          const avgTps = avg(pts.map((p) => p.tps))
          const avgCpu = avg(pts.map((p) => p.cpu_usage))
          return (
            <Card key={db} className="bg-card border-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2" style={{ color: resolveDbColor(db) }}>
                  <span className="h-2 w-2 rounded-full inline-block" style={{ backgroundColor: resolveDbColor(db) }} />
                  {getDbDisplayName(db)}
                </CardTitle>
                <CardDescription className="text-xs">{pts.length} точек данных</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg время отклика</span>
                  <span className="font-mono">{avgRt.toFixed(1)} мс</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg TPS</span>
                  <span className="font-mono">{avgTps.toFixed(1)}</span>
                </div>
                {avgCpu > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Avg CPU</span>
                    <span className="font-mono">{avgCpu.toFixed(1)}%</span>
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TimeSeriesChart
          title="Время отклика (мс)"
          icon={<Clock className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="responseTime"
          chartType="line"
          customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
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
          customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
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
          customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
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
          customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
        />
        {showCpu && (
          <TimeSeriesChart
            title="Загрузка CPU (%)"
            icon={<Cpu className="h-5 w-5 text-primary" />}
            data={chartData}
            databases={databases}
            dbNames={DB_NAMES}
            getDbColor={getDbColor}
            metricKey="cpu"
            chartType="area"
            yDomain={[0, 100]}
            customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
          />
        )}
        {showMemory && (
          <TimeSeriesChart
            title="Использование памяти (%)"
            icon={<MemoryStick className="h-5 w-5 text-primary" />}
            data={chartData}
            databases={databases}
            dbNames={DB_NAMES}
            getDbColor={getDbColor}
            metricKey="memory"
            chartType="area"
            yDomain={[0, 100]}
            customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
          />
        )}
        {showDiskIO && (
          <TimeSeriesChart
            title="Дисковые операции (IOPS)"
            icon={<Activity className="h-5 w-5 text-primary" />}
            data={chartData}
            databases={databases}
            dbNames={DB_NAMES}
            getDbColor={getDbColor}
            metricKey="diskIO"
            chartType="line"
            customDbNames={Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))}
          />
        )}
      </div>
    </div>
  )
}
