"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
  ReferenceLine,
} from "recharts"

import type { ComparisonResult } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface ComparisonChartsProps {
  result: ComparisonResult
  useNormalized?: boolean
}

const COLORS = ["#2563eb", "#dc2626", "#0f766e", "#d97706", "#7c3aed", "#0891b2", "#be185d"]

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

function toDbFamilyLabel(dbKey: string, labels?: Record<string, string>): string {
  const resolved = labels?.[dbKey] || dbKey
  const lower = resolved.toLowerCase()
  if (lower.includes("post")) return "PostgreSQL"
  if (lower.includes("maria")) return "MariaDB"
  if (lower.includes("mysql")) return "MySQL"
  return resolved
}

export function ComparisonCharts({ result, useNormalized = false }: ComparisonChartsProps) {
  const testNameById = Object.fromEntries(result.tests.map((t) => [t.id, t.name]))
  const showNormalized =
    useNormalized && (result.comparison_type === "scalability" || result.comparison_type === "mixed")

  return (
    <div className="space-y-6">
      {showNormalized ? (
        <NormalizedCharts result={result} />
      ) : (
        <RawCharts result={result} />
      )}
      <ThroughputTimeline result={result} testNameById={testNameById} showNormalized={showNormalized} />
    </div>
  )
}

function RawCharts({ result }: { result: ComparisonResult }) {
  const barData = result.charts_data.bar_chart.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    latency_mean: item.latency_mean,
    latency_p95: item.latency_p95,
    latency_p99: item.latency_p99,
    throughput_mean: item.throughput_mean,
    error_rate: item.error_rate,
  }))

  const boxData = result.charts_data.box_plot.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    min: item.min,
    q1: item.q1,
    median: item.median,
    q3: item.q3,
    max: item.max,
    iqr: item.q3 - item.q1,
    whiskerLow: item.min,
    whiskerHigh: item.max,
    sample_count: item.sample_count,
  }))

  const percentileData = result.charts_data.bar_chart.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    p50: item.latency_mean,
    p95: item.latency_p95,
    p99: item.latency_p99,
  }))

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Latency</CardTitle>
          <CardDescription>Среднее время отклика и перцентили (мс)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-15} textAnchor="end" height={64} tick={{ fontSize: 11 }} />
                <YAxis label={{ value: "мс", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="latency_mean" name="Mean" fill="#d97706" />
                <Bar dataKey="latency_p95" name="p95" fill="#ea580c" />
                <Bar dataKey="latency_p99" name="p99" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Throughput</CardTitle>
          <CardDescription>Пропускная способность (req/s)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-15} textAnchor="end" height={64} tick={{ fontSize: 11 }} />
                <YAxis label={{ value: "req/s", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="throughput_mean" name="Throughput mean" fill="#2563eb">
                  {barData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {percentileData.some((d) => d.p95 != null) && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Сравнение перцентилей latency</CardTitle>
            <CardDescription>p50 / p95 / p99 — хвостовые задержки</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={percentileData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-15} textAnchor="end" height={64} tick={{ fontSize: 11 }} />
                  <YAxis label={{ value: "мс", angle: -90, position: "insideLeft" }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="p50" name="p50 (median)" fill="#0f766e" />
                  <Bar dataKey="p95" name="p95" fill="#7c3aed" />
                  <Bar dataKey="p99" name="p99" fill="#dc2626" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {boxData.length > 0 && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Распределение latency</CardTitle>
            <CardDescription>Five-number summary: min, Q1, median, Q3, max</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={boxData} barGap={-20}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-15} textAnchor="end" height={64} tick={{ fontSize: 11 }} />
                  <YAxis label={{ value: "мс", angle: -90, position: "insideLeft" }} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0].payload
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md text-sm space-y-1">
                          <p className="font-medium">{d.name}</p>
                          <p>Min: {d.min?.toFixed(2)} мс</p>
                          <p>Q1: {d.q1?.toFixed(2)} мс</p>
                          <p>Median: {d.median?.toFixed(2)} мс</p>
                          <p>Q3: {d.q3?.toFixed(2)} мс</p>
                          <p>Max: {d.max?.toFixed(2)} мс</p>
                          <p className="text-muted-foreground">IQR: {d.iqr?.toFixed(2)} мс</p>
                          <p className="text-muted-foreground">n = {d.sample_count}</p>
                        </div>
                      )
                    }}
                  />
                  <Legend />
                  <Bar dataKey="whiskerLow" name="Min" fill="transparent" />
                  <Bar dataKey="q1" name="Q1" fill="#0f766e" fillOpacity={0.3} />
                  <Bar dataKey="median" name="Median" fill="#2563eb" />
                  <Bar dataKey="q3" name="Q3" fill="#7c3aed" fillOpacity={0.3} />
                  <Bar dataKey="whiskerHigh" name="Max" fill="transparent" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function NormalizedCharts({ result }: { result: ComparisonResult }) {
  const normalizedByThreads = buildNormalizedByThreads(result)
  const efficiencyByThreads = buildEfficiencyByThreads(result)
  const dbFamilies = Array.from(
    new Set(
      Object.values(normalizedByThreads).flatMap((item) =>
        Object.keys(item).filter((key) => key !== "threads")
      )
    )
  )

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Throughput на поток</CardTitle>
          <CardDescription>Нормализованная пропускная способность по уровням нагрузки</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={normalizedByThreads}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="threads" label={{ value: "Потоки", position: "insideBottom", offset: -5 }} />
                <YAxis label={{ value: "req/s/thread", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Legend />
                {dbFamilies.map((family, index) => (
                  <Line
                    key={family}
                    type="monotone"
                    dataKey={family}
                    name={`${family} req/s/thread`}
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Scaling efficiency</CardTitle>
          <CardDescription>Эффективность масштабирования относительно baseline (100% = идеально)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={efficiencyByThreads}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="threads" label={{ value: "Потоки", position: "insideBottom", offset: -5 }} />
                <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
                <Legend />
                <ReferenceLine y={1} stroke="#666" strokeDasharray="3 3" label="Идеально" />
                {dbFamilies.map((family, index) => (
                  <Line
                    key={family}
                    type="monotone"
                    dataKey={family}
                    name={`${family} efficiency`}
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function ThroughputTimeline({
  result,
  testNameById,
  showNormalized,
}: {
  result: ComparisonResult
  testNameById: Record<string, string>
  showNormalized: boolean
}) {
  const resolveSeriesLabel = (seriesKey: string): string => {
    const [testId, ...rest] = seriesKey.split(":")
    const dbKey = rest.join(":")
    const name = testNameById[testId] || testId
    const dbLabel = dbKey ? resolveDbKeyLabel(dbKey, result.db_key_labels) : ""
    return dbLabel ? `${name} · ${dbLabel}` : name
  }

  const seriesEntries = Object.entries(result.charts_data.throughput_series)
  if (seriesEntries.length === 0) return null

  const allSeriesData: Record<string, Array<{ relativeTime: number; throughput: number }>> = {}

  for (const [seriesKey, points] of seriesEntries) {
    const label = resolveSeriesLabel(seriesKey)
    const timestamps = points
      .map((p) => (p.timestamp ? new Date(p.timestamp).getTime() : null))
      .filter((t): t is number => t !== null)

    const minTs = timestamps.length > 0 ? Math.min(...timestamps) : 0
    allSeriesData[label] = points.map((p) => ({
      relativeTime: p.timestamp ? Math.round((new Date(p.timestamp).getTime() - minTs) / 1000) : 0,
      throughput: p.throughput ?? p.tps ?? 0,
    }))
  }

  const seriesKeys = Object.keys(allSeriesData)

  const allTimes = new Set<number>()
  for (const data of Object.values(allSeriesData)) {
    for (const pt of data) allTimes.add(pt.relativeTime)
  }
  const sortedTimes = Array.from(allTimes).sort((a, b) => a - b)

  const merged = sortedTimes.map((t) => {
    const row: Record<string, number | string> = { time: `${t}s` }
    for (const key of seriesKeys) {
      const pt = allSeriesData[key].find((p) => p.relativeTime === t)
      row[key] = pt?.throughput ?? 0
    }
    return row
  })

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle>Throughput по времени</CardTitle>
        <CardDescription>
          {showNormalized
            ? "Нормализованные временные ряды (относительное время от начала теста)"
            : "Временные ряды пропускной способности (относительное время)"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={merged}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis label={{ value: "req/s", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              {seriesKeys.map((key, index) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  name={key}
                  stroke={COLORS[index % COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

function buildNormalizedByThreads(result: ComparisonResult): Array<Record<string, number | string>> {
  const rows = new Map<number, Record<string, number | string>>()

  for (const test of result.tests) {
    const testMetrics = result.normalized_metrics[test.id] || {}
    for (const [dbKey, normalized] of Object.entries(testMetrics)) {
      if (normalized.threads == null || normalized.throughput_per_thread == null) continue

      const threads = normalized.threads
      const family = toDbFamilyLabel(dbKey, result.db_key_labels)
      const row = rows.get(threads) || { threads }
      row[family] = normalized.throughput_per_thread
      rows.set(threads, row)
    }
  }

  return Array.from(rows.values()).sort((a, b) => Number(a.threads) - Number(b.threads))
}

function buildEfficiencyByThreads(result: ComparisonResult): Array<Record<string, number | string>> {
  const rows = new Map<number, Record<string, number | string>>()

  for (const test of result.tests) {
    const testMetrics = result.normalized_metrics[test.id] || {}
    for (const [dbKey, normalized] of Object.entries(testMetrics)) {
      if (normalized.threads == null || normalized.scaling_efficiency == null) continue

      const threads = normalized.threads
      const family = toDbFamilyLabel(dbKey, result.db_key_labels)
      const row = rows.get(threads) || { threads }
      row[family] = normalized.scaling_efficiency
      rows.set(threads, row)
    }
  }

  return Array.from(rows.values()).sort((a, b) => Number(a.threads) - Number(b.threads))
}
