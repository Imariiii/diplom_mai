"use client"

import { useMemo, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  Sigma,
  AlertTriangle,
  ArrowRight,
  LayoutGrid,
  Table2,
} from "lucide-react"

import {
  type ComparisonResult,
  type PairwiseComparison,
  isPerTestResult,
  isSeriesResult,
} from "@/lib/api"
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

type ViewMode = "cards" | "table"

function extractPairwise(result: ComparisonResult): PairwiseComparison[] {
  if (isPerTestResult(result)) return result.pairwise
  if (isSeriesResult(result)) {
    return Object.values(result.per_db).flatMap((db) => db.adjacent_level_tests)
  }
  return []
}

function resolveLabel(id: string, result: ComparisonResult): string {
  if (isPerTestResult(result)) {
    return result.db_key_labels[id] ?? id
  }
  if (isSeriesResult(result)) {
    const test = result.tests.find((t) => t.id === id)
    return test?.name ?? result.db_key_labels[id] ?? id
  }
  return id
}

export function StatisticalSummary({ result }: StatisticalSummaryProps) {
  const [showOnlySignificant, setShowOnlySignificant] = useState(false)
  const [activeMetric, setActiveMetric] = useState<string>("all")
  const [activeDb, setActiveDb] = useState<string>("all")

  const allPairwise = useMemo(() => extractPairwise(result), [result])
  const autoTable = allPairwise.length >= 6
  const [viewMode, setViewMode] = useState<ViewMode>(autoTable ? "table" : "cards")

  const grouped = useMemo(() => groupByMetric(allPairwise), [allPairwise])
  const metricKeys = useMemo(() => Object.keys(grouped), [grouped])

  const dbKeys = useMemo(
    () => Array.from(new Set(allPairwise.map((p) => p.db_key))),
    [allPairwise]
  )

  const filteredEntries = metricKeys
    .filter((m) => activeMetric === "all" || m === activeMetric)
    .map((m) => {
      let items = grouped[m]
      if (showOnlySignificant) items = items.filter((p) => p.is_significant_adjusted ?? p.is_significant)
      if (activeDb !== "all") items = items.filter((p) => p.db_key === activeDb)
      return [m, items] as const
    })
    .filter(([, items]) => items.length > 0)

  const allFiltered = filteredEntries.flatMap(([, items]) => items)

  const totalSignificant = allPairwise.filter((p) => p.is_significant_adjusted ?? p.is_significant).length
  const totalLarge = allPairwise.filter(
    (p) => (p.is_significant_adjusted ?? p.is_significant) && p.effect_size_label === "large"
  ).length

  const sectionTitle = isSeriesResult(result)
    ? "Сравнения смежных уровней нагрузки"
    : "Статистические тесты"
  const sectionDesc = isSeriesResult(result)
    ? "Попарные сравнения метрик между соседними уровнями нагрузки"
    : "Попарные сравнения с baseline · p-value · Cohen\u2019s d · 95% CI"

  return (
    <section className="space-y-4">
      <div className="rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Sigma className="h-3.5 w-3.5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-tight">{sectionTitle}</h2>
              <p className="text-xs text-muted-foreground">{sectionDesc}</p>
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
              <Label htmlFor="sig-filter" className="cursor-pointer text-xs text-muted-foreground">
                Только значимые
              </Label>
              <Switch id="sig-filter" checked={showOnlySignificant} onCheckedChange={setShowOnlySignificant} />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-b border-border/60 px-4 pt-3 pb-3">
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

          {dbKeys.length > 1 && (
            <Tabs value={activeDb} onValueChange={setActiveDb}>
              <TabsList className="h-8 bg-transparent p-0 gap-1">
                <TabsTrigger
                  value="all"
                  className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
                >
                  Все СУБД
                </TabsTrigger>
                {dbKeys.map((db) => (
                  <TabsTrigger
                    key={db}
                    value={db}
                    className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
                  >
                    {resolveDbKeyLabel(db, result.db_key_labels)}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}

          <div className="ml-auto flex items-center gap-1 rounded-md border border-border/60 bg-muted/30 p-0.5">
            <button
              onClick={() => setViewMode("cards")}
              className={`rounded p-1.5 ${viewMode === "cards" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              title="Карточки"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`rounded p-1.5 ${viewMode === "table" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              title="Таблица"
            >
              <Table2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {viewMode === "cards" ? (
          <div className="divide-y divide-border/60">
            {filteredEntries.map(([metric, items]) => (
              <div key={metric} className="p-4">
                <div className="mb-3 flex items-center gap-2">
                  <h3 className="text-sm font-medium">{METRIC_LABELS[metric] || metric}</h3>
                  <Badge variant="outline" className="font-mono text-[10px]">{items.length}</Badge>
                </div>
                <div className="grid gap-2 lg:grid-cols-2">
                  {items.map((item) => (
                    <ComparisonCard
                      key={`${item.baseline_id}-${item.compared_id}-${item.db_key}-${item.metric}`}
                      item={item}
                      result={result}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <CompactTable items={allFiltered} result={result} />
        )}

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
    </section>
  )
}

function CompactTable({
  items,
  result,
}: {
  items: PairwiseComparison[]
  result: ComparisonResult
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border/60 bg-muted/30 text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2 text-left font-medium">Сравнение</th>
            <th className="px-3 py-2 text-left font-medium">СУБД</th>
            <th className="px-3 py-2 text-left font-medium">Метрика</th>
            <th className="px-3 py-2 text-center font-medium">p-value</th>
            <th className="px-3 py-2 text-center font-medium">Cohen&apos;s d</th>
            <th className="px-3 py-2 text-center font-medium">Δ%</th>
            <th className="px-3 py-2 text-center font-medium">Эффект</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {items.map((item) => {
            const comparedName = resolveLabel(item.compared_id, result)
            const effectKey = item.effect_size_label || "negligible"
            const effectCfg = EFFECT_VARIANTS[effectKey]

            return (
              <tr
                key={`${item.baseline_id}-${item.compared_id}-${item.db_key}-${item.metric}`}
                className={`hover:bg-muted/20 ${(item.is_significant_adjusted ?? item.is_significant) ? "" : "opacity-60"}`}
              >
                <td className="px-4 py-2 font-medium">{comparedName}</td>
                <td className="px-3 py-2 text-muted-foreground">
                  {resolveDbKeyLabel(item.db_key, result.db_key_labels)}
                </td>
                <td className="px-3 py-2">{METRIC_LABELS[item.metric] || item.metric}</td>
                <td className="px-3 py-2 text-center font-mono tabular-nums">
                  {item.p_value_adjusted != null
                    ? item.p_value_adjusted.toExponential(1)
                    : item.p_value != null
                      ? item.p_value.toExponential(1)
                      : "—"}
                </td>
                <td className="px-3 py-2 text-center font-mono tabular-nums">
                  {item.effect_size != null ? Math.abs(item.effect_size).toFixed(2) : "—"}
                </td>
                <td className="px-3 py-2 text-center font-mono tabular-nums">
                  {item.pct_difference != null
                    ? `${item.pct_difference >= 0 ? "+" : ""}${item.pct_difference.toFixed(1)}%`
                    : "—"}
                </td>
                <td className="px-3 py-2 text-center">
                  <Badge variant="outline" className={`gap-1 font-mono text-[10px] ${effectCfg.cls}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${effectCfg.dotCls}`} />
                    {effectCfg.label}
                  </Badge>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ComparisonCard({
  item,
  result,
}: {
  item: PairwiseComparison
  result: ComparisonResult
}) {
  const baselineName = resolveLabel(item.baseline_id, result)
  const comparedName = resolveLabel(item.compared_id, result)

  const effectKey = item.effect_size_label || "negligible"
  const effectCfg = EFFECT_VARIANTS[effectKey]

  const unit = item.metric === "latency_ms" ? "мс" : "req/s"

  return (
    <div
      className={`relative rounded-lg border p-3 ${
        (item.is_significant_adjusted ?? item.is_significant)
          ? "border-border bg-muted/20"
          : "border-dashed border-border/60 bg-transparent"
      }`}
    >
      {(item.is_significant_adjusted ?? item.is_significant) && effectKey !== "negligible" && (
        <div className={`absolute inset-y-0 left-0 w-1 rounded-l-lg ${effectCfg.dotCls}`} />
      )}

      <div className="flex items-start justify-between gap-3 pl-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {(item.is_significant_adjusted ?? item.is_significant) ? (
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

      <div className="mt-3 flex flex-wrap gap-1.5 pl-2">
        {item.effect_size != null && item.effect_size_label && (
          <Badge variant="outline" className={`gap-1 font-mono text-[10px] ${effectCfg.cls}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${effectCfg.dotCls}`} />
            d = {Math.abs(item.effect_size).toFixed(2)} · {effectCfg.label}
          </Badge>
        )}
        <Badge variant="outline" className="font-mono text-[10px]">
          p = {item.p_value_adjusted != null ? item.p_value_adjusted.toExponential(1) : item.p_value != null ? item.p_value.toExponential(1) : "—"}
        </Badge>
        {item.test_used && (
          <Badge variant="outline" className="text-[10px]">
            {item.test_used}
          </Badge>
        )}
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
