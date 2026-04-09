"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  TooltipProps,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { ComparisonResult } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface ComparisonChartsProps {
  result: ComparisonResult
  useNormalized?: boolean
}

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

const COMPARISON_TYPE_LABELS: Record<ComparisonResult["comparison_type"], string> = {
  cross_database: "Сравнение СУБД",
  scalability: "Анализ масштабируемости",
  mixed: "Смешанное сравнение",
  temporal: "Временное сравнение",
}

export function ComparisonCharts({ result, useNormalized = false }: ComparisonChartsProps) {
  const barData = result.charts_data.bar_chart.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    latency_mean: item.latency_mean,
    latency_p95: item.latency_p95,
    throughput_mean: item.throughput_mean,
  }))

  const boxData = result.charts_data.box_plot.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    min: item.min,
    q1: item.q1,
    median: item.median,
    q3: item.q3,
    max: item.max,
  }))

  const testNameById = Object.fromEntries(result.tests.map((t) => [t.id, t.name]))

  const resolveSeriesLabel = (seriesKey: string): string => {
    const [testId, ...rest] = seriesKey.split(":")
    const dbKey = rest.join(":")
    const name = testNameById[testId] || testId
    const dbLabel = dbKey ? resolveDbKeyLabel(dbKey, result.db_key_labels) : ""
    return dbLabel ? `${name} · ${dbLabel}` : name
  }

  const throughputData = Object.entries(result.charts_data.throughput_series).flatMap(([seriesKey, points]) => {
    const label = resolveSeriesLabel(seriesKey)
    return points.map((point) => ({
      key: label,
      timestamp: point.timestamp ? new Date(point.timestamp).toLocaleTimeString("ru-RU") : "",
      throughput: point.throughput ?? point.tps ?? 0,
    }))
  })

  const normalizedByThreads = buildNormalizedByThreads(result)
  const efficiencyByThreads = buildEfficiencyByThreads(result)
  const dbFamilies = Array.from(
    new Set(
      Object.values(normalizedByThreads).flatMap((item) =>
        Object.keys(item).filter((key) => key !== "threads")
      )
    )
  )
  const throughputSeriesKeys = Array.from(new Set(throughputData.map((item) => item.key)))
  const throughputTimelineData = mergeTimeSeriesByKey(throughputData, throughputSeriesKeys)
  const showNormalizedCharts = useNormalized && (
    result.comparison_type === "scalability" || result.comparison_type === "mixed"
  )

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      {showNormalizedCharts ? (
        <>
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Throughput на поток</CardTitle>
              <CardDescription>{COMPARISON_TYPE_LABELS[result.comparison_type]} по уровням нагрузки</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={normalizedByThreads}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="threads" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    {dbFamilies.map((family, index) => (
                      <Line
                        key={family}
                        type="monotone"
                        dataKey={family}
                        name={`${family} req/s/thread`}
                        stroke={NORMALIZED_COLORS[index % NORMALIZED_COLORS.length]}
                        dot
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
              <CardDescription>Нормализованная эффективность относительно baseline</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={efficiencyByThreads}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="threads" />
                    <YAxis tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                    <Tooltip formatter={(value: number) => `${(value * 100).toFixed(1)}%`} />
                    <Legend />
                    {dbFamilies.map((family, index) => (
                      <Line
                        key={family}
                        type="monotone"
                        dataKey={family}
                        name={`${family} efficiency`}
                        stroke={NORMALIZED_COLORS[index % NORMALIZED_COLORS.length]}
                        dot
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Средние значения</CardTitle>
            <CardDescription>Latency и throughput по всем сравниваемым тестам</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-18} textAnchor="end" height={64} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="latency_mean" name="Latency mean (мс)" fill="#d97706" />
                  <Bar dataKey="latency_p95" name="Latency p95 (мс)" fill="#dc2626" />
                  <Bar dataKey="throughput_mean" name="Throughput mean (req/s)" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {!showNormalizedCharts && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Box plot latency</CardTitle>
            <CardDescription>Five-number summary по latency samples</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={boxData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-18} textAnchor="end" height={64} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="min" name="Min" stroke="#64748b" dot={false} />
                  <Line type="monotone" dataKey="q1" name="Q1" stroke="#0f766e" dot={false} />
                  <Line type="monotone" dataKey="median" name="Median" stroke="#2563eb" dot={false} />
                  <Line type="monotone" dataKey="q3" name="Q3" stroke="#7c3aed" dot={false} />
                  <Line type="monotone" dataKey="max" name="Max" stroke="#dc2626" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="bg-card border-border xl:col-span-2">
        <CardHeader>
          <CardTitle>{showNormalizedCharts ? "Динамика throughput по тестам" : "Throughput over time"}</CardTitle>
          <CardDescription>
            {showNormalizedCharts
              ? "Сопоставление временных рядов помогает увидеть устойчивость после нормализации"
              : "Исторические временные ряды из time_series"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={throughputTimelineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                {throughputSeriesKeys.map((seriesKey, index) => (
                  <Line
                    key={seriesKey}
                    type="monotone"
                    dataKey={seriesKey}
                    name={seriesKey}
                    stroke={NORMALIZED_COLORS[index % NORMALIZED_COLORS.length]}
                    dot={false}
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

const NORMALIZED_COLORS = ["#2563eb", "#dc2626", "#0f766e", "#d97706", "#7c3aed"]

function buildNormalizedByThreads(result: ComparisonResult): Array<Record<string, number | string>> {
  const rows = new Map<number, Record<string, number | string>>()

  for (const test of result.tests) {
    const testMetrics = result.normalized_metrics[test.id] || {}
    for (const [dbKey, normalized] of Object.entries(testMetrics)) {
      if (normalized.threads == null || normalized.throughput_per_thread == null) {
        continue
      }

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
      if (normalized.threads == null || normalized.scaling_efficiency == null) {
        continue
      }

      const threads = normalized.threads
      const family = toDbFamilyLabel(dbKey, result.db_key_labels)
      const row = rows.get(threads) || { threads }
      row[family] = normalized.scaling_efficiency
      rows.set(threads, row)
    }
  }

  return Array.from(rows.values()).sort((a, b) => Number(a.threads) - Number(b.threads))
}

function mergeTimeSeriesByKey(
  flatRows: Array<{ key: string; timestamp: string; throughput: number }>
,
  seriesKeys: string[],
): Array<Record<string, number | string>> {
  const rows = new Map<string, Record<string, number | string>>()

  for (const item of flatRows) {
    const row = rows.get(item.timestamp) || { timestamp: item.timestamp }
    row[item.key] = item.throughput
    rows.set(item.timestamp, row)
  }

  const merged = Array.from(rows.values())
  return merged.map((row) => {
    for (const key of seriesKeys) {
      if (!(key in row)) {
        row[key] = 0
      }
    }
    return row
  })
}

function toDbFamilyLabel(dbKey: string, labels?: Record<string, string>): string {
  const resolved = labels?.[dbKey] || dbKey
  const lower = resolved.toLowerCase()
  if (lower.includes("post")) return "PostgreSQL"
  if (lower.includes("mysql")) return "MySQL"
  return resolved
}
