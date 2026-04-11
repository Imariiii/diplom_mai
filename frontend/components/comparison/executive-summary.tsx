"use client"

import { TrendingUp, TrendingDown, Minus, Activity, Zap, Timer, AlertTriangle } from "lucide-react"

import type { ComparisonResult } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface ExecutiveSummaryProps {
  result: ComparisonResult
}

const COMPARISON_TYPE_LABELS: Record<ComparisonResult["comparison_type"], string> = {
  cross_database: "Сравнение СУБД",
  scalability: "Анализ масштабируемости",
  mixed: "Смешанное сравнение",
  temporal: "Временное сравнение",
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
  const bestLatency = findBestMetric(result, "latency", "lower")
  const verdict = result.analysis_report?.verdict || ""

  const verdictColor =
    sigCount === 0
      ? "border-muted-foreground/20 bg-muted/30"
      : largeEffects.length > 0
        ? "border-primary/30 bg-primary/5"
        : "border-amber-500/30 bg-amber-500/5"

  return (
    <Card className={`border-2 ${verdictColor}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl">Результат сравнения</CardTitle>
          <div className="flex gap-2">
            <Badge variant="secondary">{COMPARISON_TYPE_LABELS[result.comparison_type]}</Badge>
            <Badge variant="outline">{result.tests.length} тестов</Badge>
          </div>
        </div>
        {verdict && (
          <p className="text-base text-foreground leading-relaxed mt-2">{verdict}</p>
        )}
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            icon={<Activity className="h-5 w-5" />}
            label="Статистически значимых"
            value={`${sigCount} / ${totalComparisons}`}
            detail={sigCount > 0 ? "попарных сравнений" : "различий не обнаружено"}
            variant={sigCount > 0 ? "positive" : "neutral"}
          />

          {bestThroughput && (
            <KpiCard
              icon={<Zap className="h-5 w-5" />}
              label="Лучший throughput"
              value={`${bestThroughput.value.toFixed(1)} req/s`}
              detail={bestThroughput.testName}
              variant="positive"
            />
          )}

          {bestLatency && (
            <KpiCard
              icon={<Timer className="h-5 w-5" />}
              label="Лучшая latency"
              value={`${bestLatency.value.toFixed(2)} мс`}
              detail={bestLatency.testName}
              variant="positive"
            />
          )}

          <KpiCard
            icon={largeEffects.length > 0 ? <TrendingUp className="h-5 w-5" /> : <Minus className="h-5 w-5" />}
            label="Практически значимых"
            value={`${largeEffects.length}`}
            detail="различий с medium/large эффектом"
            variant={largeEffects.length > 0 ? "accent" : "neutral"}
          />
        </div>

        {result.warnings.length > 0 && (
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-600 mb-1">
              <AlertTriangle className="h-4 w-4" />
              Предупреждения ({result.warnings.length})
            </div>
            <div className="space-y-0.5 text-sm text-muted-foreground">
              {result.warnings.slice(0, 3).map((w) => (
                <p key={w}>• {w}</p>
              ))}
              {result.warnings.length > 3 && (
                <p className="text-xs">и ещё {result.warnings.length - 3}...</p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function KpiCard({
  icon,
  label,
  value,
  detail,
  variant,
}: {
  icon: React.ReactNode
  label: string
  value: string
  detail: string
  variant: "positive" | "negative" | "neutral" | "accent"
}) {
  const colors = {
    positive: "text-green-600",
    negative: "text-red-600",
    neutral: "text-muted-foreground",
    accent: "text-primary",
  }

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-1">
      <div className={`flex items-center gap-2 text-sm ${colors[variant]}`}>
        {icon}
        <span>{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground truncate">{detail}</p>
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
      const val =
        type === "throughput"
          ? bundle.throughput?.mean
          : bundle.latency_ms?.mean
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
