"use client"

import { useMemo } from "react"
import {
  Activity,
  Zap,
  Timer,
  TrendingUp,
  CheckCircle2,
  Trophy,
  Target,
} from "lucide-react"

import type { ComparisonResult } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

interface ExecutiveSummaryProps {
  result: ComparisonResult
}

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

export function ExecutiveSummary({ result }: ExecutiveSummaryProps) {
  const sigCount = result.pairwise_comparisons.filter((p) => p.is_significant).length
  const totalComparisons = result.pairwise_comparisons.length
  const largeEffects = result.pairwise_comparisons.filter(
    (p) => p.is_significant && (p.effect_size_label === "large" || p.effect_size_label === "medium")
  )

  const bestThroughput = findBestMetric(result, "throughput", "higher")
  const worstThroughput = findBestMetric(result, "throughput", "lower")
  const bestLatency = findBestMetric(result, "latency", "lower")
  const worstLatency = findBestMetric(result, "latency", "higher")

  const verdict = result.analysis_report?.verdict || ""

  const intensity =
    sigCount === 0
      ? "neutral"
      : largeEffects.length >= 3
        ? "strong"
        : largeEffects.length > 0
          ? "moderate"
          : "weak"

  const showTrends = result.tests.length >= 3

  return (
    <section
      aria-label="Результат сравнения"
      className="relative overflow-hidden rounded-xl border border-border bg-card"
    >
      <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-primary via-primary to-primary/40" />

      <div className="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
        {/* Left: Verdict text */}
        <div className="space-y-4 p-6 lg:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5 border-primary/30 bg-primary/5 text-primary">
              <Trophy className="h-3 w-3" />
              Ключевой вывод
            </Badge>
            <IntensityBadge intensity={intensity} />
          </div>

          <h2 className="text-pretty text-xl font-semibold leading-snug tracking-tight md:text-[1.35rem]">
            {verdict || "Статистически значимых различий между тестами не обнаружено."}
          </h2>

          {bestThroughput && bestLatency && (
            <div className="grid gap-2 pt-2 sm:grid-cols-2">
              <WinnerPill
                icon={<Zap className="h-3.5 w-3.5" />}
                label="Лидер throughput"
                name={bestThroughput.testName}
                db={resolveDbKeyLabel(bestThroughput.dbKey, result.db_key_labels)}
                value={`${bestThroughput.value.toFixed(0)} req/s`}
              />
              <WinnerPill
                icon={<Timer className="h-3.5 w-3.5" />}
                label="Лидер latency"
                name={bestLatency.testName}
                db={resolveDbKeyLabel(bestLatency.dbKey, result.db_key_labels)}
                value={`${bestLatency.value.toFixed(2)} мс`}
              />
            </div>
          )}
        </div>

        {/* Right: KPI grid */}
        <div className="grid grid-cols-2 gap-px border-t border-border bg-border lg:border-t-0 lg:border-l">
          <KpiTile
            icon={<Activity className="h-3.5 w-3.5" />}
            label="Значимых"
            primary={`${sigCount}`}
            secondary={`из ${totalComparisons} сравнений`}
            progress={totalComparisons > 0 ? sigCount / totalComparisons : 0}
            tone="primary"
          />
          <KpiTile
            icon={<Target className="h-3.5 w-3.5" />}
            label="Large/Medium effects"
            primary={`${largeEffects.length}`}
            secondary="практических различий"
            progress={totalComparisons > 0 ? largeEffects.length / totalComparisons : 0}
            tone={largeEffects.length > 0 ? "accent" : "neutral"}
          />
          <KpiTile
            icon={<TrendingUp className="h-3.5 w-3.5" />}
            label="Throughput диапазон"
            primary={
              bestThroughput
                ? `${bestThroughput.value.toFixed(0)} req/s`
                : "—"
            }
            secondary={
              worstThroughput && bestThroughput && worstThroughput.value !== bestThroughput.value
                ? `min ${worstThroughput.value.toFixed(0)} req/s`
                : "по всем тестам"
            }
            tone="success"
          />
          <KpiTile
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            label="Latency диапазон"
            primary={bestLatency ? `${bestLatency.value.toFixed(2)} мс` : "—"}
            secondary={
              worstLatency && bestLatency && worstLatency.value !== bestLatency.value
                ? `max ${worstLatency.value.toFixed(2)} мс`
                : "по всем тестам"
            }
            tone="neutral"
          />
        </div>
      </div>

      {/* Sparkline trends strip for 3+ tests */}
      {showTrends && <TestTrendsStrip result={result} />}
    </section>
  )
}

// ---------- TestTrendsStrip ----------

function TestTrendsStrip({ result }: { result: ComparisonResult }) {
  const trends = useMemo(() => buildTrendData(result), [result])

  if (trends.length === 0) return null

  return (
    <div className="border-t border-border px-6 py-4">
      <p className="mb-3 text-[11px] uppercase tracking-wider text-muted-foreground">
        Тренды по тестам
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {trends.map((t) => (
          <div key={t.key} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium">{t.label}</span>
              <span className="font-mono text-muted-foreground tabular-nums">
                {t.unit}
              </span>
            </div>
            <MiniSparkline values={t.values} />
          </div>
        ))}
      </div>
    </div>
  )
}

interface TrendSeries {
  key: string
  label: string
  unit: string
  values: number[]
}

function buildTrendData(result: ComparisonResult): TrendSeries[] {
  const dbKeys = Array.from(
    new Set(
      Object.values(result.descriptive_stats).flatMap((bm) => Object.keys(bm))
    )
  )
  const series: TrendSeries[] = []

  for (const dbKey of dbKeys) {
    const dbLabel = resolveDbKeyLabel(dbKey, result.db_key_labels)
    const tpValues: number[] = []
    const latValues: number[] = []

    for (const test of result.tests) {
      const bundle = result.descriptive_stats[test.id]?.[dbKey]
      tpValues.push(bundle?.throughput?.mean ?? 0)
      latValues.push(bundle?.latency_ms?.mean ?? 0)
    }

    if (tpValues.some((v) => v > 0)) {
      series.push({
        key: `tp-${dbKey}`,
        label: `${dbLabel} · Throughput`,
        unit: "req/s",
        values: tpValues,
      })
    }
    if (latValues.some((v) => v > 0)) {
      series.push({
        key: `lat-${dbKey}`,
        label: `${dbLabel} · Latency`,
        unit: "мс",
        values: latValues,
      })
    }
  }

  return series
}

function MiniSparkline({ values }: { values: number[] }) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const h = 24
  const w = 100

  const points = values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * w
      const y = h - ((v - min) / range) * (h - 4) - 2
      return `${x},${y}`
    })
    .join(" ")

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-6 w-full text-primary"
      preserveAspectRatio="none"
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ---------- Sub-components ----------

function IntensityBadge({ intensity }: { intensity: "strong" | "moderate" | "weak" | "neutral" }) {
  const map = {
    strong: { label: "Сильные различия", cls: "bg-warning/15 text-warning border-warning/30" },
    moderate: { label: "Умеренные различия", cls: "bg-primary/10 text-primary border-primary/20" },
    weak: { label: "Слабые эффекты", cls: "bg-muted text-muted-foreground border-border" },
    neutral: { label: "Эффекты не выражены", cls: "bg-muted text-muted-foreground border-border" },
  } as const
  const cfg = map[intensity]
  return (
    <Badge variant="outline" className={cfg.cls}>
      {cfg.label}
    </Badge>
  )
}

function WinnerPill({
  icon,
  label,
  name,
  db,
  value,
}: {
  icon: React.ReactNode
  label: string
  name: string
  db: string
  value: string
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-success/15 text-success">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {label}
          </p>
          <p className="truncate text-sm font-medium">
            {name}
            <span className="text-muted-foreground"> · {db}</span>
          </p>
        </div>
      </div>
      <p className="shrink-0 font-mono text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function KpiTile({
  icon,
  label,
  primary,
  secondary,
  progress,
  tone,
}: {
  icon: React.ReactNode
  label: string
  primary: string
  secondary: string
  progress?: number
  tone: "primary" | "accent" | "success" | "neutral"
}) {
  const toneMap = {
    primary: "text-primary",
    accent: "text-warning",
    success: "text-success",
    neutral: "text-muted-foreground",
  } as const

  const barColor = {
    primary: "bg-primary",
    accent: "bg-warning",
    success: "bg-success",
    neutral: "bg-muted-foreground/60",
  } as const

  return (
    <div className="bg-card p-4 md:p-5">
      <div className="flex items-center gap-2">
        <span className={toneMap[tone]}>{icon}</span>
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums leading-none">
        {primary}
      </p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{secondary}</p>
      {progress != null && (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${barColor[tone]}`}
            style={{ width: `${Math.min(100, Math.max(4, progress * 100))}%` }}
          />
        </div>
      )}
    </div>
  )
}

function findBestMetric(
  result: ComparisonResult,
  type: "throughput" | "latency",
  direction: "higher" | "lower"
): { testName: string; value: number; dbKey: string } | null {
  let best: { testName: string; value: number; dbKey: string } | null = null
  for (const test of result.tests) {
    const bundles = result.descriptive_stats[test.id] || {}
    for (const [dbKey, bundle] of Object.entries(bundles)) {
      const val = type === "throughput" ? bundle.throughput?.mean : bundle.latency_ms?.mean
      if (val == null) continue
      if (
        !best ||
        (direction === "higher" && val > best.value) ||
        (direction === "lower" && val < best.value)
      ) {
        best = { testName: test.name, value: val, dbKey }
      }
    }
  }
  return best
}
