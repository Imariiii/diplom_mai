"use client"

import { useMemo, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Sigma,
  AlertTriangle,
  ArrowRight,
} from "lucide-react"

import type { ComparisonResult, PairwiseComparison } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

interface StatisticalSummaryProps {
  result: ComparisonResult
}

const METRIC_ORDER = ["latency_ms", "throughput", "throughput_per_thread", "scaling_efficiency"]
const METRIC_LABELS: Record<string, string> = {
  latency_ms: "Latency",
  throughput: "Throughput",
  throughput_per_thread: "Throughput на поток",
  scaling_efficiency: "Scaling efficiency",
}

const EFFECT_VARIANTS: Record<
  string,
  { cls: string; dotCls: string; label: string }
> = {
  large: {
    cls: "bg-warning/10 text-warning border-warning/30",
    dotCls: "bg-warning",
    label: "большой",
  },
  medium: {
    cls: "bg-primary/10 text-primary border-primary/30",
    dotCls: "bg-primary",
    label: "средний",
  },
  small: {
    cls: "bg-muted text-muted-foreground border-border",
    dotCls: "bg-muted-foreground/60",
    label: "малый",
  },
  negligible: {
    cls: "bg-muted text-muted-foreground border-border",
    dotCls: "bg-muted-foreground/30",
    label: "пренебрежимый",
  },
}

export function StatisticalSummary({ result }: StatisticalSummaryProps) {
  const [showOnlySignificant, setShowOnlySignificant] = useState(false)
  const [activeMetric, setActiveMetric] = useState<string>("all")

  const grouped = useMemo(() => groupByMetric(result.pairwise_comparisons), [result])
  const metricKeys = useMemo(() => Object.keys(grouped), [grouped])

  const filteredEntries = metricKeys
    .filter((m) => activeMetric === "all" || m === activeMetric)
    .map((m) => {
      const items = showOnlySignificant
        ? grouped[m].filter((p) => p.is_significant)
        : grouped[m]
      return [m, items] as const
    })
    .filter(([, items]) => items.length > 0)

  const totalSignificant = result.pairwise_comparisons.filter((p) => p.is_significant).length
  const totalLarge = result.pairwise_comparisons.filter(
    (p) => p.is_significant && p.effect_size_label === "large"
  ).length

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-border bg-card">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Sigma className="h-3.5 w-3.5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-tight">
                Статистические тесты
              </h2>
              <p className="text-xs text-muted-foreground">
                Попарные сравнения с baseline · p-value · Cohen&apos;s d · 95% CI
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5">
              <CheckCircle2 className="h-3 w-3 text-success" />
              <span className="font-mono tabular-nums">{totalSignificant}</span> значимых
            </Badge>
            <Badge variant="outline" className="gap-1.5">
              <AlertTriangle className="h-3 w-3 text-warning" />
              <span className="font-mono tabular-nums">{totalLarge}</span> large effect
            </Badge>
            <div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2 py-1">
              <Label
                htmlFor="sig-filter"
                className="cursor-pointer text-xs text-muted-foreground"
              >
                Только значимые
              </Label>
              <Switch
                id="sig-filter"
                checked={showOnlySignificant}
                onCheckedChange={setShowOnlySignificant}
              />
            </div>
          </div>
        </div>

        {/* Metric tabs */}
        <div className="border-b border-border/60 px-4 pt-3">
          <Tabs value={activeMetric} onValueChange={setActiveMetric}>
            <TabsList className="h-8 bg-transparent p-0 gap-1">
              <TabsTrigger
                value="all"
                className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
              >
                Все метрики
              </TabsTrigger>
              {metricKeys.map((m) => (
                <TabsTrigger
                  key={m}
                  value={m}
                  className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
                >
                  {METRIC_LABELS[m] || m}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        {/* Body */}
        <div className="divide-y divide-border/60">
          {filteredEntries.map(([metric, items]) => (
            <div key={metric} className="p-4">
              <div className="mb-3 flex items-center gap-2">
                <h3 className="text-sm font-medium">
                  {METRIC_LABELS[metric] || metric}
                </h3>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {items.length}
                </Badge>
              </div>
              <div className="grid gap-2 lg:grid-cols-2">
                {items.map((item) => (
                  <ComparisonCard
                    key={`${item.baseline_test_id}-${item.compared_test_id}-${item.db_key}-${item.metric}`}
                    item={item}
                    result={result}
                  />
                ))}
              </div>
            </div>
          ))}

          {filteredEntries.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-2 p-10 text-center">
              <AlertCircle className="h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                {showOnlySignificant
                  ? "Статистически значимых различий не обнаружено"
                  : "Попарные сравнения отсутствуют"}
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function ComparisonCard({
  item,
  result,
}: {
  item: PairwiseComparison
  result: ComparisonResult
}) {
  const baselineName =
    result.tests.find((t) => t.id === item.baseline_test_id)?.name ||
    item.baseline_test_id
  const comparedName =
    result.tests.find((t) => t.id === item.compared_test_id)?.name ||
    item.compared_test_id

  const effectKey = item.effect_size_label || "negligible"
  const effectCfg = EFFECT_VARIANTS[effectKey]

  const unit = item.metric === "latency_ms" ? "мс" : "req/s"

  return (
    <div
      className={`relative rounded-lg border p-3 ${
        item.is_significant
          ? "border-border bg-muted/20"
          : "border-dashed border-border/60 bg-transparent"
      }`}
    >
      {/* Significance stripe */}
      {item.is_significant && effectKey !== "negligible" && (
        <div className={`absolute inset-y-0 left-0 w-1 rounded-l-lg ${effectCfg.dotCls}`} />
      )}

      <div className="flex items-start justify-between gap-3 pl-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {item.is_significant ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate text-sm font-medium">
              {resolveDbKeyLabel(item.db_key, result.db_key_labels)}
            </span>
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-1 pl-6 font-mono text-xs text-muted-foreground">
            <span>{baselineName}</span>
            <ArrowRight className="h-3 w-3" />
            <span>{comparedName}</span>
          </div>

          <p className="mt-2 pl-6 text-sm leading-relaxed text-foreground/80">
            {item.interpretation}
          </p>

          {item.ci_lower != null && item.ci_upper != null && (
            <p className="mt-1.5 pl-6 font-mono text-[11px] text-muted-foreground">
              95% CI: [{item.ci_lower.toFixed(2)}, {item.ci_upper.toFixed(2)}] {unit}
            </p>
          )}

          {item.warning && (
            <div className="mt-2 flex items-start gap-1.5 rounded-md bg-warning/5 px-2 py-1.5 pl-2 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              <span>{item.warning}</span>
            </div>
          )}
        </div>
      </div>

      {/* Metric pills */}
      <div className="mt-3 flex flex-wrap gap-1.5 pl-2">
        {item.effect_size != null && item.effect_size_label && (
          <Badge
            variant="outline"
            className={`gap-1 font-mono text-[10px] ${effectCfg.cls}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${effectCfg.dotCls}`} />
            d = {Math.abs(item.effect_size).toFixed(2)} · {effectCfg.label}
          </Badge>
        )}
        <Badge
          variant="outline"
          className="font-mono text-[10px]"
        >
          p = {item.p_value != null ? item.p_value.toExponential(1) : "—"}
        </Badge>
        <Badge variant="outline" className="text-[10px]">
          {item.test_used}
        </Badge>
      </div>
    </div>
  )
}

function groupByMetric(
  comparisons: PairwiseComparison[]
): Record<string, PairwiseComparison[]> {
  const groups: Record<string, PairwiseComparison[]> = {}
  const sorted = [...comparisons].sort((a, b) => {
    const aIdx = METRIC_ORDER.indexOf(a.metric)
    const bIdx = METRIC_ORDER.indexOf(b.metric)
    return (aIdx === -1 ? 99 : aIdx) - (bIdx === -1 ? 99 : bIdx)
  })
  for (const item of sorted) {
    if (!groups[item.metric]) groups[item.metric] = []
    groups[item.metric].push(item)
  }
  return groups
}
