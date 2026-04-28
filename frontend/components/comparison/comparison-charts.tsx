"use client"

import { useMemo, useState } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { BarChart3, LineChart as LineIcon, Activity, Maximize2 } from "lucide-react"

import {
  type ComparisonResult,
  type BarChartPoint,
  type SeriesChartPoint,
  isPerTestResult,
  isSeriesResult,
} from "@/lib/api"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface ComparisonChartsProps {
  result: ComparisonResult
  chartFocus?: "degradation" | "stability"
}

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

const DB_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

export function ComparisonCharts({ result, chartFocus }: ComparisonChartsProps) {
  if (isPerTestResult(result)) {
    return <PerTestChartsView result={result} />
  }
  if (isSeriesResult(result)) {
    return <SeriesChartsView result={result} chartFocus={chartFocus} />
  }
  return null
}

// ═══════════════════════════════════════════════════════════════════════════
// Per-test charts
// ═══════════════════════════════════════════════════════════════════════════

function PerTestChartsView({ result }: { result: Extract<ComparisonResult, { analysis_mode: "per_test" }> }) {
  const charts = result.charts

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <GroupedLatencyChart barData={charts.bar_chart} dbKeyLabels={result.db_key_labels} />
      <GroupedThroughputChart barData={charts.bar_chart} dbKeyLabels={result.db_key_labels} />
      <PercentilesChart barData={charts.bar_chart} dbKeyLabels={result.db_key_labels} />
      <DistributionChart boxData={charts.box_plot} dbKeyLabels={result.db_key_labels} />
      <div className="xl:col-span-2">
        <ThroughputTimeline
          series={charts.throughput_series}
          dbKeyLabels={result.db_key_labels}
        />
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Series charts
// ═══════════════════════════════════════════════════════════════════════════

function SeriesChartsView({
  result,
  chartFocus,
}: {
  result: Extract<ComparisonResult, { analysis_mode: "series" }>
  chartFocus?: "degradation" | "stability"
}) {
  const charts = result.charts

  if (chartFocus === "degradation") {
    return (
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SeriesTrajectoryChart
          title="Задержка p95 по уровням нагрузки"
          description="Деградация хвостовых задержек (p95)"
          data={charts.p95_by_load}
          dbKeyLabels={result.db_key_labels}
          unit="мс"
        />
        <SeriesTrajectoryChart
          title="Задержка p99 по уровням нагрузки"
          description="Деградация хвостовых задержек (p99)"
          data={charts.p99_by_load}
          dbKeyLabels={result.db_key_labels}
          unit="мс"
        />
        <DegradationSummaryChart result={result} />
      </div>
    )
  }

  if (chartFocus === "stability") {
    return (
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SeriesTrajectoryChart
          title="Доля ошибок по уровням нагрузки"
          description="Доля ошибок при росте нагрузки"
          data={charts.error_rate_by_load}
          dbKeyLabels={result.db_key_labels}
          unit="%"
        />
        {Object.keys(charts.scaling_efficiency).length > 0 && (
          <SeriesTrajectoryChart
            title="Эффективность масштабирования"
            description="Коэффициент масштабирования при росте нагрузки"
            data={charts.scaling_efficiency}
            dbKeyLabels={result.db_key_labels}
            unit="%"
          />
        )}
        <StabilityIndexChart result={result} />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <SeriesTrajectoryChart
        title="Пропускная способность по уровням нагрузки"
        description="Средняя пропускная способность на каждом уровне"
        data={charts.throughput_by_load}
        dbKeyLabels={result.db_key_labels}
        unit="зап/с"
      />
      <SeriesTrajectoryChart
        title="Задержка по уровням нагрузки"
        description="Средняя задержка на каждом уровне"
        data={charts.latency_by_load}
        dbKeyLabels={result.db_key_labels}
        unit="мс"
      />
      <SeriesTrajectoryChart
        title="Задержка p95 по уровням нагрузки"
        description="Хвостовые задержки p95"
        data={charts.p95_by_load}
        dbKeyLabels={result.db_key_labels}
        unit="мс"
      />
      <SeriesTrajectoryChart
        title="Задержка p99 по уровням нагрузки"
        description="Хвостовые задержки p99"
        data={charts.p99_by_load}
        dbKeyLabels={result.db_key_labels}
        unit="мс"
      />
      {charts.bar_chart.length > 0 && (
        <GroupedThroughputChart barData={charts.bar_chart} dbKeyLabels={result.db_key_labels} />
      )}
      {charts.box_plot.length > 0 && (
        <DistributionChart boxData={charts.box_plot} dbKeyLabels={result.db_key_labels} />
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Generic chart card shell
// ═══════════════════════════════════════════════════════════════════════════

function ChartCard({
  title,
  description,
  icon: Icon = BarChart3,
  children,
  className,
  badge,
  chartHeight = 280,
}: {
  title: string
  description: string
  icon?: React.ElementType
  children: React.ReactNode
  className?: string
  badge?: React.ReactNode
  chartHeight?: number
}) {
  const [fullscreen, setFullscreen] = useState(false)

  const header = (
    <div className="flex items-start gap-2.5 min-w-0">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )

  return (
    <>
      <div className={`flex flex-col rounded-xl border border-border bg-card ${className ?? ""}`}>
        <div className="flex items-start justify-between gap-3 border-b border-border/60 p-4">
          {header}
          <div className="flex items-center gap-1 shrink-0">
            {badge}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={() => setFullscreen(true)}
              title="Развернуть"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <div className="p-4">
          <div style={{ height: chartHeight }}>
            {children}
          </div>
        </div>
      </div>

      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-[calc(100vw-2rem)] w-[calc(100vw-2rem)] h-[calc(100vh-2rem)] max-h-[calc(100vh-2rem)] flex flex-col gap-0 p-0">
          <DialogHeader className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-border/60">
            <DialogTitle className="flex items-center gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Icon className="h-3.5 w-3.5" />
              </div>
              {title}
            </DialogTitle>
            <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
          </DialogHeader>
          <div className="flex-1 min-h-0 p-6">
            {children}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Shared per-test charts (grouped bar / percentiles / distribution / timeline)
// ═══════════════════════════════════════════════════════════════════════════

interface GroupedDataPoint {
  testName: string
  [dbLabel: string]: string | number | null | undefined
}

function buildGroupedData(
  barData: BarChartPoint[],
  dbKeyLabels: Record<string, string>,
  getValue: (pt: BarChartPoint) => number | null | undefined
): { data: GroupedDataPoint[]; dbLabels: string[] } {
  const testNames = Array.from(new Set(barData.map((d) => d.label)))
  const dbKeysRaw = Array.from(new Set(barData.map((d) => d.db_key)))
  const dbLabels = dbKeysRaw.map((k) => resolveDbKeyLabel(k, dbKeyLabels))
  const dbKeyToLabel = Object.fromEntries(
    dbKeysRaw.map((k, i) => [k, dbLabels[i]])
  )

  const data: GroupedDataPoint[] = testNames.map((name) => {
    const row: GroupedDataPoint = { testName: name }
    for (const pt of barData.filter((d) => d.label === name)) {
      const label = dbKeyToLabel[pt.db_key] || pt.db_key
      row[label] = getValue(pt)
    }
    return row
  })

  return { data, dbLabels: Array.from(new Set(dbLabels)) }
}

function GroupedLatencyChart({
  barData,
  dbKeyLabels,
}: {
  barData: BarChartPoint[]
  dbKeyLabels: Record<string, string>
}) {
  const { data, dbLabels } = useMemo(
    () => buildGroupedData(barData, dbKeyLabels, (pt) => pt.latency_mean),
    [barData, dbKeyLabels]
  )

  const config: ChartConfig = Object.fromEntries(
    dbLabels.map((label, i) => [label, { label, color: DB_COLORS[i % DB_COLORS.length] }])
  )

  return (
    <ChartCard title="Задержка" description="Среднее по СУБД (мс)" icon={Activity}>
      <ChartContainer config={config} className="h-full w-full">
        <BarChart data={data} barGap={2} barCategoryGap="20%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="testName" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="dot" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {dbLabels.map((label, i) => (
            <Bar key={label} dataKey={label} radius={[4, 4, 0, 0]} fill={DB_COLORS[i % DB_COLORS.length]} />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

function GroupedThroughputChart({
  barData,
  dbKeyLabels,
}: {
  barData: BarChartPoint[]
  dbKeyLabels: Record<string, string>
}) {
  const { data, dbLabels } = useMemo(
    () => buildGroupedData(barData, dbKeyLabels, (pt) => pt.throughput_mean),
    [barData, dbKeyLabels]
  )

  const maxVal = Math.max(...barData.map((d) => d.throughput_mean ?? 0), 1)

  const config: ChartConfig = Object.fromEntries(
    dbLabels.map((label, i) => [label, { label, color: DB_COLORS[i % DB_COLORS.length] }])
  )

  return (
    <ChartCard
      title="Пропускная способность"
      description="Пропускная способность по СУБД (зап/с)"
      icon={BarChart3}
      badge={
        <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
          макс {Math.round(maxVal).toLocaleString()} зап/с
        </span>
      }
    >
      <ChartContainer config={config} className="h-full w-full">
        <BarChart data={data} barGap={2} barCategoryGap="20%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="testName" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {dbLabels.map((label, i) => (
            <Bar key={label} dataKey={label} radius={[4, 4, 0, 0]} fill={DB_COLORS[i % DB_COLORS.length]} />
          ))}
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

function PercentilesChart({
  barData,
  dbKeyLabels,
}: {
  barData: BarChartPoint[]
  dbKeyLabels: Record<string, string>
}) {
  const hasPercentiles = barData.some((d) => d.latency_p95 != null)
  if (!hasPercentiles) return null

  const data = barData.map((item) => ({
    name: `${item.label} · ${resolveDbKeyLabel(item.db_key, dbKeyLabels)}`,
    p50: item.latency_p50,
    p95: item.latency_p95,
    p99: item.latency_p99,
  }))

  const config: ChartConfig = {
    p50: { label: "p50 (median)", color: "var(--chart-3)" },
    p95: { label: "p95", color: "var(--chart-4)" },
    p99: { label: "p99", color: "var(--chart-5)" },
  }

  return (
    <ChartCard title="Перцентили задержки" description="p50 / p95 / p99 — хвостовые задержки" icon={LineIcon}>
      <ChartContainer config={config} className="h-full w-full">
        <LineChart data={data}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
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

function DistributionChart({
  boxData,
  dbKeyLabels,
}: {
  boxData: Array<{ label: string; db_key: string; min: number; q1: number; median: number; q3: number; max: number; sample_count: number }>
  dbKeyLabels: Record<string, string>
}) {
  if (boxData.length === 0) return null

  const mapped = boxData.map((d) => ({
    name: `${d.label} · ${resolveDbKeyLabel(d.db_key, dbKeyLabels)}`,
    min: d.min,
    q1Offset: d.q1 - d.min,
    medianOffset: d.median - d.q1,
    q3Offset: d.q3 - d.median,
    maxOffset: d.max - d.q3,
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
    <ChartCard title="Распределение задержки" description="Пятичисловой анализ (мин · Q1 · медиана · Q3 · макс)" icon={BarChart3}>
      <ChartContainer config={config} className="h-full w-full">
        <BarChart data={mapped} layout="vertical" stackOffset="expand">
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} width={140} />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.3 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload
              return (
                <div className="rounded-lg border border-border bg-popover p-2.5 text-xs shadow-md">
                  <p className="font-medium">{d.name}</p>
                  <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono tabular-nums">
                    <span className="text-muted-foreground">мин</span>
                    <span>{d.min.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">Q1</span>
                    <span>{d.q1.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">медиана</span>
                    <span className="font-semibold">{d.median.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">Q3</span>
                    <span>{d.q3.toFixed(2)} мс</span>
                    <span className="text-muted-foreground">макс</span>
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

function ThroughputTimeline({
  series,
  dbKeyLabels,
}: {
  series: Record<string, Array<{ timestamp?: string | null; throughput?: number | null; tps?: number | null }>>
  dbKeyLabels: Record<string, string>
}) {
  const { merged, seriesKeys } = useMemo(() => {
    const resolveSeriesLabel = (seriesKey: string) => {
      const parts = seriesKey.split(":")
      const dbKey = parts.length > 1 ? parts.slice(1).join(":") : seriesKey
      return resolveDbKeyLabel(dbKey, dbKeyLabels)
    }

    const seriesEntries = Object.entries(series)
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
  }, [series, dbKeyLabels])

  if (merged.length === 0) return null

  const config: ChartConfig = Object.fromEntries(
    seriesKeys.map((k, i) => [k, { label: k, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return (
    <ChartCard
      title="Пропускная способность по времени"
      description="Временные ряды пропускной способности (относительное время)"
      icon={LineIcon}
      chartHeight={320}
    >
      <ChartContainer config={config} className="h-full w-full">
        <LineChart data={merged}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} interval="preserveStartEnd" minTickGap={32} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ChartLegend content={<ChartLegendContent />} />
          {seriesKeys.map((key) => (
            <Line key={key} type="monotone" dataKey={key} stroke={`var(--color-${key})`} strokeWidth={1.75} dot={false} />
          ))}
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Series-specific charts
// ═══════════════════════════════════════════════════════════════════════════

function SeriesTrajectoryChart({
  title,
  description,
  data,
  dbKeyLabels,
  unit,
}: {
  title: string
  description: string
  data: Record<string, SeriesChartPoint[]>
  dbKeyLabels: Record<string, string>
  unit: string
}) {
  const { chartData, dbLabels } = useMemo(() => {
    const entries = Object.entries(data)
    if (entries.length === 0) return { chartData: [], dbLabels: [] }

    const dbLabels = entries.map(([k]) => resolveDbKeyLabel(k, dbKeyLabels))

    const allLevels = entries[0][1].map((pt) => pt.load_label)
    const chartData = allLevels.map((label, idx) => {
      const row: Record<string, string | number | null> = { load: label }
      entries.forEach(([dbKey, points], dbIdx) => {
        const dbLabel = dbLabels[dbIdx]
        row[dbLabel] = points[idx]?.value ?? null
      })
      return row
    })

    return { chartData, dbLabels }
  }, [data, dbKeyLabels])

  if (chartData.length === 0) return null

  const config: ChartConfig = Object.fromEntries(
    dbLabels.map((label, i) => [label, { label, color: DB_COLORS[i % DB_COLORS.length] }])
  )

  return (
    <ChartCard title={title} description={description} icon={LineIcon}>
      <ChartContainer config={config} className="h-full w-full">
        <LineChart data={chartData}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="load" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => (unit === "%" ? `${v.toFixed(0)}%` : `${v}`)}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                indicator="dot"
                formatter={(value, name) => (
                  <div className="flex w-full justify-between gap-4">
                    <span className="text-muted-foreground">{name}</span>
                    <span className="font-mono font-medium tabular-nums">
                      {typeof value === "number" ? (unit === "зап/с" ? value.toFixed(0) : value.toFixed(2)) : "—"} {unit}
                    </span>
                  </div>
                )}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          {dbLabels.map((label, i) => (
            <Line
              key={label}
              type="monotone"
              dataKey={label}
              stroke={DB_COLORS[i % DB_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ChartContainer>
    </ChartCard>
  )
}

function DegradationSummaryChart({
  result,
}: {
  result: Extract<ComparisonResult, { analysis_mode: "series" }>
}) {
  const data = useMemo(() => {
    return Object.entries(result.per_db).map(([dbKey, summary]) => ({
      name: resolveDbKeyLabel(dbKey, result.db_key_labels),
      p95: summary.degradation.overall_p95,
      p99: summary.degradation.overall_p99,
    }))
  }, [result])

  if (data.length === 0) return null

  const config: ChartConfig = {
    p95: { label: "Деградация p95", color: "var(--chart-4)" },
    p99: { label: "Деградация p99", color: "var(--chart-5)" },
  }

  return (
    <ChartCard
      title="Индекс деградации"
      description="Суммарная деградация p95/p99 по СУБД"
      icon={Activity}
    >
      <ChartContainer config={config} className="h-full w-full">
        <BarChart data={data} barGap={4} barCategoryGap="30%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                indicator="dot"
                formatter={(value) => (
                  <span className="font-mono tabular-nums">
                    {((value as number) * 100).toFixed(1)}%
                  </span>
                )}
              />
            }
          />
          <ChartLegend content={<ChartLegendContent />} />
          <Bar dataKey="p95" radius={[4, 4, 0, 0]} fill="var(--chart-4)" />
          <Bar dataKey="p99" radius={[4, 4, 0, 0]} fill="var(--chart-5)" />
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}

function StabilityIndexChart({
  result,
}: {
  result: Extract<ComparisonResult, { analysis_mode: "series" }>
}) {
  const data = useMemo(() => {
    return Object.entries(result.per_db)
      .filter(([, s]) => s.stability_index != null)
      .map(([dbKey, summary]) => ({
        name: resolveDbKeyLabel(dbKey, result.db_key_labels),
        stability: summary.stability_index,
        elasticity: summary.elasticity,
      }))
  }, [result])

  if (data.length === 0) return null

  const config: ChartConfig = {
    stability: { label: "Индекс стабильности", color: "var(--chart-1)" },
    elasticity: { label: "Эластичность", color: "var(--chart-3)" },
  }

  return (
    <ChartCard
      title="Стабильность и эластичность"
      description="CV-индекс стабильности и эластичность пропускной способности"
      icon={Activity}
    >
      <ChartContainer config={config} className="h-full w-full">
        <BarChart data={data} barGap={4} barCategoryGap="30%">
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10 }} />
          <ChartTooltip content={<ChartTooltipContent indicator="dot" />} />
          <ChartLegend content={<ChartLegendContent />} />
          <Bar dataKey="stability" radius={[4, 4, 0, 0]} fill="var(--chart-1)" />
          <Bar dataKey="elasticity" radius={[4, 4, 0, 0]} fill="var(--chart-3)" />
        </BarChart>
      </ChartContainer>
    </ChartCard>
  )
}
