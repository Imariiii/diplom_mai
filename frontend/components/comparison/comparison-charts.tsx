"use client"

import { useMemo } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
  ReferenceLine,
  Cell,
} from "recharts"
import { BarChart3, LineChart as LineIcon, Activity } from "lucide-react"

import type { ComparisonResult, BarChartPoint } from "@/lib/api"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"

interface ComparisonChartsProps {
  result: ComparisonResult
  useNormalized?: boolean
}

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

const DB_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

export function ComparisonCharts({ result, useNormalized = false }: ComparisonChartsProps) {
  const testNameById = Object.fromEntries(result.tests.map((t) => [t.id, t.name]))
  const showNormalized =
    useNormalized && (result.comparison_type === "scalability" || result.comparison_type === "mixed")

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {showNormalized ? (
        <>
          <NormalizedThroughputChart result={result} />
          <ScalingEfficiencyChart result={result} />
        </>
      ) : (
        <>
          <GroupedLatencyChart result={result} />
          <GroupedThroughputChart result={result} />
          <PercentilesChart result={result} />
          <DistributionChart result={result} />
        </>
      )}
      <div className="xl:col-span-2">
        <ThroughputTimeline
          result={result}
          testNameById={testNameById}
          showNormalized={showNormalized}
        />
      </div>
    </div>
  )
}

// ---------- Chart shell ----------

function ChartCard({
  title,
  description,
  icon: Icon = BarChart3,
  children,
  className,
  badge,
}: {
  title: string
  description: string
  icon?: React.ElementType
  children: React.ReactNode
  className?: string
  badge?: React.ReactNode
}) {
  return (
    <div className={`flex flex-col rounded-xl border border-border bg-card ${className ?? ""}`}>
      <div className="flex items-start justify-between gap-3 border-b border-border/60 p-4">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icon className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
        {badge}
      </div>
      <div className="flex-1 p-4">{children}</div>
    </div>
  )
}

// ---------- Grouped charts helpers ----------

interface GroupedDataPoint {
  testName: string
  [dbLabel: string]: string | number | null | undefined
}

function buildGroupedData(
  barData: BarChartPoint[],
  dbKeyLabels: Record<string, string>,
  getValue: (pt: BarChartPoint) => number | null | undefined
): { data: GroupedDataPoint[]; dbLabels: string[] } {
  const testNames = Array.from(new Set(barData.map((d) => d.test_name)))
  const dbKeysRaw = Array.from(new Set(barData.map((d) => d.db_key)))
  const dbLabels = dbKeysRaw.map((k) => resolveDbKeyLabel(k, dbKeyLabels))
  const dbKeyToLabel = Object.fromEntries(
    dbKeysRaw.map((k, i) => [k, dbLabels[i]])
  )

  const data: GroupedDataPoint[] = testNames.map((name) => {
    const row: GroupedDataPoint = { testName: name }
    for (const pt of barData.filter((d) => d.test_name === name)) {
      const label = dbKeyToLabel[pt.db_key] || pt.db_key
      row[label] = getValue(pt)
    }
    return row
  })

  return { data, dbLabels: Array.from(new Set(dbLabels)) }
}

// ---------- Grouped Latency Chart ----------

function GroupedLatencyChart({ result }: { result: ComparisonResult }) {
  const { data, dbLabels } = useMemo(
    () =>
      buildGroupedData(
        result.charts_data.bar_chart,
        result.db_key_labels,
        (pt) => pt.latency_mean
      ),
    [result]
  )

  const config: ChartConfig = Object.fromEntries(
    dbLabels.map((label, i) => [
      label,
      { label, color: DB_COLORS[i % DB_COLORS.length] },
    ])
  )

  return (
    <ChartCard
      title="Latency"
      description="Среднее по СУБД (мс)"
      icon={Activity}
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <BarChart data={data} barGap={2} barCategoryGap="20%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="testName"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => `${v}`}
          />
          <ChartTooltip content={<ChartTooltipContent indicator="dot" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {dbLabels.map((label, i) => (
            <Bar
              key={label}
              dataKey={label}
              radius={[4, 4, 0, 0]}
              fill={DB_COLORS[i % DB_COLORS.length]}
            />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Grouped Throughput Chart ----------

function GroupedThroughputChart({ result }: { result: ComparisonResult }) {
  const { data, dbLabels } = useMemo(
    () =>
      buildGroupedData(
        result.charts_data.bar_chart,
        result.db_key_labels,
        (pt) => pt.throughput_mean
      ),
    [result]
  )

  const maxVal = Math.max(
    ...result.charts_data.bar_chart.map((d) => d.throughput_mean ?? 0),
    1
  )

  const config: ChartConfig = Object.fromEntries(
    dbLabels.map((label, i) => [
      label,
      { label, color: DB_COLORS[i % DB_COLORS.length] },
    ])
  )

  return (
    <ChartCard
      title="Throughput"
      description="Пропускная способность по СУБД (req/s)"
      icon={BarChart3}
      badge={
        <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
          max {Math.round(maxVal).toLocaleString()} req/s
        </span>
      }
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <BarChart data={data} barGap={2} barCategoryGap="20%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="testName"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11 }}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {dbLabels.map((label, i) => (
            <Bar
              key={label}
              dataKey={label}
              radius={[4, 4, 0, 0]}
              fill={DB_COLORS[i % DB_COLORS.length]}
            />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Percentiles ----------

function PercentilesChart({ result }: { result: ComparisonResult }) {
  const hasPercentiles = result.charts_data.bar_chart.some((d) => d.latency_p95 != null)
  if (!hasPercentiles) return null

  const data = result.charts_data.bar_chart.map((item) => ({
    name: `${item.test_name} · ${resolveDbKeyLabel(item.db_key, result.db_key_labels)}`,
    p50: item.latency_mean,
    p95: item.latency_p95,
    p99: item.latency_p99,
  }))

  const config: ChartConfig = {
    p50: { label: "p50 (median)", color: "var(--chart-3)" },
    p95: { label: "p95", color: "var(--chart-4)" },
    p99: { label: "p99", color: "var(--chart-5)" },
  }

  return (
    <ChartCard
      title="Перцентили latency"
      description="p50 / p95 / p99 — хвостовые задержки"
      icon={LineIcon}
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <LineChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="dot" />} />
          <ChartLegend content={<ChartLegendContent />} />
          <Line type="monotone" dataKey="p50" stroke="var(--color-p50)" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="p95" stroke="var(--color-p95)" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="p99" stroke="var(--color-p99)" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Distribution ----------

function DistributionChart({ result }: { result: ComparisonResult }) {
  const data = result.charts_data.box_plot
  if (data.length === 0) return null

  const mapped = data.map((d) => ({
    name: `${d.test_name} · ${resolveDbKeyLabel(d.db_key, result.db_key_labels)}`,
    min: d.min,
    q1Offset: d.q1 - d.min,
    medianOffset: d.median - d.q1,
    q3Offset: d.q3 - d.median,
    maxOffset: d.max - d.q3,
    iqr: d.q3 - d.q1,
    median: d.median,
    q1: d.q1,
    q3: d.q3,
    max: d.max,
    sample_count: d.sample_count,
  }))

  const config: ChartConfig = {
    q1Offset: { label: "min → Q1", color: "var(--chart-2)" },
    medianOffset: { label: "Q1 → median", color: "var(--chart-3)" },
    q3Offset: { label: "median → Q3", color: "var(--chart-3)" },
    maxOffset: { label: "Q3 → max", color: "var(--chart-2)" },
  }

  return (
    <ChartCard
      title="Распределение latency"
      description="Five-number summary (min · Q1 · median · Q3 · max)"
      icon={BarChart3}
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <BarChart data={mapped} layout="vertical" stackOffset="expand">
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <YAxis
            type="category"
            dataKey="name"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            width={140}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.3 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="rounded-lg border border-border bg-popover p-2.5 text-xs shadow-md">
                  <p className="font-medium">{d.name}</p>
                  <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono tabular-nums">
                    <span className="text-muted-foreground">min</span>
                    <span>{d.min.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">Q1</span>
                    <span>{d.q1.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">median</span>
                    <span className="font-semibold">{d.median.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">Q3</span>
                    <span>{d.q3.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">max</span>
                    <span>{d.max.toFixed(2)} мс</span>
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">n = {d.sample_count}</p>
                </div>
              )
            }}
          />
          <Bar dataKey="min" stackId="a" fill="transparent" />
          <Bar dataKey="q1Offset" stackId="a" fill="var(--chart-2)" fillOpacity={0.4} />
          <Bar dataKey="medianOffset" stackId="a" fill="var(--chart-3)" />
          <Bar dataKey="q3Offset" stackId="a" fill="var(--chart-3)" fillOpacity={0.6} />
          <Bar dataKey="maxOffset" stackId="a" fill="var(--chart-2)" fillOpacity={0.4} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Normalized charts ----------

function NormalizedThroughputChart({ result }: { result: ComparisonResult }) {
  const data = buildByThreads(result, "throughput_per_thread")
  const families = extractFamilies(data)

  const config: ChartConfig = Object.fromEntries(
    families.map((f, i) => [f, { label: f, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return (
    <ChartCard
      title="Throughput на поток"
      description="Нормализованная пропускная способность по уровням нагрузки"
      icon={LineIcon}
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <LineChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="threads"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            label={{ value: "Потоки", position: "insideBottom", offset: -4, fontSize: 10 }}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {families.map((family) => (
            <Line
              key={family}
              type="monotone"
              dataKey={family}
              stroke={`var(--color-${family})`}
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

function ScalingEfficiencyChart({ result }: { result: ComparisonResult }) {
  const data = buildByThreads(result, "scaling_efficiency")
  const families = extractFamilies(data)

  const config: ChartConfig = Object.fromEntries(
    families.map((f, i) => [f, { label: f, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return (
    <ChartCard
      title="Scaling efficiency"
      description="Эффективность масштабирования относительно baseline (100% = идеально)"
      icon={Activity}
    >
      <ChartContainer config={config} className="h-[280px] w-full">
        <LineChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="threads"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
            domain={[0, 1.1]}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                indicator="line"
                formatter={(value, name, item) => (
                  <div className="flex w-full justify-between gap-4">
                    <span className="text-muted-foreground">{item.dataKey}</span>
                    <span className="font-mono font-medium tabular-nums">
                      {((value as number) * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          <ReferenceLine
            y={1}
            stroke="var(--muted-foreground)"
            strokeDasharray="3 3"
            label={{ value: "Идеально", fontSize: 10, fill: "var(--muted-foreground)" }}
          />
          {families.map((family) => (
            <Line
              key={family}
              type="monotone"
              dataKey={family}
              stroke={`var(--color-${family})`}
              strokeWidth={2}
              dot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Throughput Timeline ----------

function ThroughputTimeline({
  result,
  testNameById,
  showNormalized,
}: {
  result: ComparisonResult
  testNameById: Record<string, string>
  showNormalized: boolean
}) {
  const { merged, seriesKeys } = useMemo(() => {
    const resolveSeriesLabel = (seriesKey: string) => {
      const [testId, ...rest] = seriesKey.split(":")
      const dbKey = rest.join(":")
      const dbLabel = dbKey ? resolveDbKeyLabel(dbKey, result.db_key_labels) : ""
      return dbLabel || testId
    }

    const seriesEntries = Object.entries(result.charts_data.throughput_series)
    if (seriesEntries.length === 0) return { merged: [], seriesKeys: [] as string[] }

    const all: Record<string, Array<{ t: number; v: number }>> = {}
    for (const [k, points] of seriesEntries) {
      const label = resolveSeriesLabel(k)
      const times = points
        .map((p) => (p.timestamp ? new Date(p.timestamp).getTime() : null))
        .filter((t): t is number => t !== null)
      const min = times.length ? Math.min(...times) : 0
      all[label] = points.map((p) => ({
        t: p.timestamp ? Math.round((new Date(p.timestamp).getTime() - min) / 1000) : 0,
        v: p.throughput ?? p.tps ?? 0,
      }))
    }

    const allT = new Set<number>()
    for (const s of Object.values(all)) for (const p of s) allT.add(p.t)
    const sortedT = Array.from(allT).sort((a, b) => a - b)

    const m = sortedT.map((t) => {
      const row: Record<string, number | string> = { time: `${t}s` }
      for (const key of Object.keys(all)) {
        const pt = all[key].find((p) => p.t === t)
        row[key] = pt?.v ?? 0
      }
      return row
    })
    return { merged: m, seriesKeys: Object.keys(all) }
  }, [result, testNameById])

  if (merged.length === 0) return null

  const config: ChartConfig = Object.fromEntries(
    seriesKeys.map((k, i) => [k, { label: k, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return (
    <ChartCard
      title="Throughput по времени"
      description={
        showNormalized
          ? "Нормализованные временные ряды (относительное время)"
          : "Временные ряды пропускной способности (относительное время)"
      }
      icon={LineIcon}
    >
      <ChartContainer config={config} className="h-[320px] w-full">
        <LineChart data={merged}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="time"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
            minTickGap={32}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {seriesKeys.map((key) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={`var(--color-${key})`}
              strokeWidth={1.75}
              dot={false}
            />
          ))}
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ---------- Helpers ----------

function buildByThreads(
  result: ComparisonResult,
  field: "throughput_per_thread" | "scaling_efficiency"
): Array<Record<string, number | string>> {
  const rows = new Map<number, Record<string, number | string>>()
  for (const test of result.tests) {
    const metrics = result.normalized_metrics[test.id] || {}
    for (const [dbKey, n] of Object.entries(metrics)) {
      const threads = n.threads
      const value = n[field]
      if (threads == null || value == null) continue
      const family = toDbFamilyLabel(dbKey, result.db_key_labels)
      const row = rows.get(threads) || { threads }
      row[family] = value
      rows.set(threads, row)
    }
  }
  return Array.from(rows.values()).sort((a, b) => Number(a.threads) - Number(b.threads))
}

function extractFamilies(data: Array<Record<string, number | string>>): string[] {
  return Array.from(new Set(data.flatMap((d) => Object.keys(d).filter((k) => k !== "threads"))))
}
