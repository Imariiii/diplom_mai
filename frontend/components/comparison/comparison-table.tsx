"use client"

import { useMemo, useState } from "react"
import { Crown, TrendingDown, TrendingUp, Minus, Table2 } from "lucide-react"

import type {
  ComparisonResult,
  MetricStatsBundle,
  NormalizedMetrics,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

interface ComparisonTableProps {
  result: ComparisonResult
  useNormalized?: boolean
}

type CellView = "values" | "delta" | "both"

interface MetricRow {
  key: string
  label: string
  better: "lower" | "higher"
  isCore: boolean
  unit: string
  accessor: (
    bundle: MetricStatsBundle | undefined,
    normalized: NormalizedMetrics | undefined
  ) => number | null | undefined
  format: (value: number | null | undefined) => string
}

const RAW_METRIC_ROWS: MetricRow[] = [
  { key: "latency_mean", label: "Latency mean", better: "lower", isCore: true, unit: "мс", accessor: (b) => b?.latency_ms?.mean, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_median", label: "Latency median", better: "lower", isCore: true, unit: "мс", accessor: (b) => b?.latency_ms?.median, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_p95", label: "Latency p95", better: "lower", isCore: true, unit: "мс", accessor: (b) => b?.latency_ms?.p95, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_p99", label: "Latency p99", better: "lower", isCore: true, unit: "мс", accessor: (b) => b?.latency_ms?.p99, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_cv", label: "Latency CV", better: "lower", isCore: true, unit: "%", accessor: (b) => b?.latency_ms?.cv, format: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`) },
  { key: "throughput_mean", label: "Throughput mean", better: "higher", isCore: true, unit: "req/s", accessor: (b) => b?.throughput?.mean, format: (v) => (v == null ? "—" : `${v.toFixed(0)} req/s`) },
  { key: "error_rate", label: "Error rate", better: "lower", isCore: true, unit: "%", accessor: (b) => b?.error_rate, format: (v) => (v == null ? "—" : `${v.toFixed(2)}%`) },
  { key: "duration", label: "Общее время", better: "lower", isCore: true, unit: "с", accessor: (b) => b?.total_duration_sec, format: (v) => (v == null ? "—" : `${v.toFixed(1)} с`) },
  { key: "latency_min", label: "Latency min", better: "lower", isCore: false, unit: "мс", accessor: (b) => b?.latency_ms?.min, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_max", label: "Latency max", better: "lower", isCore: false, unit: "мс", accessor: (b) => b?.latency_ms?.max, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "latency_iqr", label: "Latency IQR", better: "lower", isCore: false, unit: "мс", accessor: (b) => b?.latency_ms?.iqr, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "throughput_median", label: "Throughput median", better: "higher", isCore: false, unit: "req/s", accessor: (b) => b?.throughput?.median, format: (v) => (v == null ? "—" : `${v.toFixed(0)} req/s`) },
  { key: "throughput_cv", label: "Throughput CV", better: "lower", isCore: false, unit: "%", accessor: (b) => b?.throughput?.cv, format: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`) },
]

const NORMALIZED_METRIC_ROWS: MetricRow[] = [
  { key: "throughput_abs", label: "Throughput absolute", better: "higher", isCore: true, unit: "req/s", accessor: (_, n) => n?.throughput_abs, format: (v) => (v == null ? "—" : `${v.toFixed(0)} req/s`) },
  { key: "throughput_per_thread", label: "Throughput / thread", better: "higher", isCore: true, unit: "req/s", accessor: (_, n) => n?.throughput_per_thread, format: (v) => (v == null ? "—" : `${v.toFixed(1)} req/s`) },
  { key: "scaling_efficiency", label: "Scaling efficiency", better: "higher", isCore: true, unit: "%", accessor: (_, n) => n?.scaling_efficiency, format: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`) },
  { key: "latency_mean_abs", label: "Latency absolute", better: "lower", isCore: true, unit: "мс", accessor: (_, n) => n?.latency_mean_abs, format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`) },
  { key: "threads", label: "Потоки", better: "higher", isCore: true, unit: "", accessor: (_, n) => n?.threads, format: (v) => (v == null ? "—" : `${v.toFixed(0)}`) },
  { key: "duration_seconds", label: "Длительность", better: "lower", isCore: true, unit: "с", accessor: (_, n) => n?.duration_seconds, format: (v) => (v == null ? "—" : `${v.toFixed(1)} с`) },
  { key: "throughput_per_second", label: "Throughput по duration", better: "higher", isCore: false, unit: "req/s", accessor: (_, n) => n?.throughput_per_second, format: (v) => (v == null ? "—" : `${v.toFixed(1)} req/s`) },
  { key: "latency_per_thread", label: "Latency на поток", better: "lower", isCore: false, unit: "мс", accessor: (_, n) => n?.latency_per_thread, format: (v) => (v == null ? "—" : `${v.toFixed(4)} мс`) },
]

export function ComparisonTable({ result, useNormalized = false }: ComparisonTableProps) {
  const [showExtended, setShowExtended] = useState(false)
  const [cellView, setCellView] = useState<CellView>("both")

  const dbKeys = useMemo(
    () =>
      Array.from(
        new Set(
          Object.values(result.descriptive_stats).flatMap((bm) => Object.keys(bm))
        )
      ),
    [result]
  )

  const [activeDb, setActiveDb] = useState(dbKeys[0] ?? "")

  const allMetricRows = useNormalized ? NORMALIZED_METRIC_ROWS : RAW_METRIC_ROWS
  const metricRows = showExtended
    ? allMetricRows
    : allMetricRows.filter((r) => r.isCore)
  const hasExtended = allMetricRows.some((r) => !r.isCore)

  return (
    <section className="rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Table2 className="h-3.5 w-3.5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Детальные метрики</h2>
            <p className="text-xs text-muted-foreground">
              Построчное сравнение · зелёным отмечено лучшее значение
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="gap-1 font-mono text-[11px]">
            <Crown className="h-3 w-3" />
            Baseline: {result.tests.find((t) => t.id === result.baseline_id)?.name}
          </Badge>
          {hasExtended && (
            <div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2 py-1">
              <Label htmlFor="extended-metrics" className="cursor-pointer text-xs text-muted-foreground">
                Все метрики
              </Label>
              <Switch
                id="extended-metrics"
                checked={showExtended}
                onCheckedChange={setShowExtended}
              />
            </div>
          )}
        </div>
      </div>

      {/* DB tabs + view mode toggle */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border/60 px-4 pt-3 pb-3">
        {dbKeys.length > 1 && (
          <Tabs value={activeDb} onValueChange={setActiveDb}>
            <TabsList className="h-8 bg-transparent p-0 gap-1">
              {dbKeys.map((dbKey) => (
                <TabsTrigger
                  key={dbKey}
                  value={dbKey}
                  className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
                >
                  {resolveDbKeyLabel(dbKey, result.db_key_labels)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}

        <div className="ml-auto">
          <Tabs value={cellView} onValueChange={(v) => setCellView(v as CellView)}>
            <TabsList className="h-8 bg-transparent p-0 gap-1">
              <TabsTrigger
                value="values"
                className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
              >
                Значения
              </TabsTrigger>
              <TabsTrigger
                value="delta"
                className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
              >
                Δ%
              </TabsTrigger>
              <TabsTrigger
                value="both"
                className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50"
              >
                Оба
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      {/* Table body */}
      <div className="overflow-x-auto">
        <MetricTable
          result={result}
          dbKey={dbKeys.length > 1 ? activeDb : dbKeys[0] ?? ""}
          metricRows={metricRows}
          cellView={cellView}
        />
      </div>
    </section>
  )
}

function MetricTable({
  result,
  dbKey,
  metricRows,
  cellView,
}: {
  result: ComparisonResult
  dbKey: string
  metricRows: MetricRow[]
  cellView: CellView
}) {
  const baselineId = result.baseline_id

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border/60 bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <th className="px-4 py-2.5 text-left font-medium">Метрика</th>
          {result.tests.map((test) => (
            <th
              key={test.id}
              className="px-4 py-2.5 text-left font-medium"
            >
              <div className="flex items-center gap-1.5">
                {test.name}
                {test.id === baselineId && (
                  <Crown className="h-3 w-3 text-primary" />
                )}
              </div>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {metricRows.map((metricRow) => {
          const values = result.tests
            .map((t) => metricRow.accessor(
              result.descriptive_stats[t.id]?.[dbKey],
              result.normalized_metrics[t.id]?.[dbKey]
            ))
            .filter((v): v is number => typeof v === "number")
          const bestValue =
            values.length === 0
              ? null
              : metricRow.better === "lower"
                ? Math.min(...values)
                : Math.max(...values)
          const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1)

          const baselineBundle = result.descriptive_stats[baselineId]?.[dbKey]
          const baselineNormalized = result.normalized_metrics[baselineId]?.[dbKey]
          const baselineValue = metricRow.accessor(baselineBundle, baselineNormalized)

          return (
            <tr
              key={`${dbKey}-${metricRow.key}`}
              className="border-b border-border/60 last:border-b-0 hover:bg-muted/20"
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{metricRow.label}</span>
                  <Badge
                    variant="outline"
                    className="h-4 px-1 font-mono text-[9px] uppercase"
                  >
                    {metricRow.better === "lower" ? "↓ lower" : "↑ higher"}
                  </Badge>
                </div>
              </td>
              {result.tests.map((test) => {
                const bundle = result.descriptive_stats[test.id]?.[dbKey]
                const normalized = result.normalized_metrics[test.id]?.[dbKey]
                const value = metricRow.accessor(bundle, normalized)
                const isBest = bestValue != null && value === bestValue
                const diff =
                  baselineValue == null || baselineValue === 0 || value == null
                    ? null
                    : ((value - baselineValue) / baselineValue) * 100
                const diffIsGood =
                  diff != null &&
                  ((metricRow.better === "lower" && diff < 0) ||
                    (metricRow.better === "higher" && diff > 0))

                const isBaseline = test.id === baselineId

                const showValues = cellView === "values" || cellView === "both"
                const showDelta = (cellView === "delta" || cellView === "both") && !isBaseline

                const barWidth =
                  value == null ? 0 : Math.min(100, (Math.abs(value) / maxAbs) * 100)

                return (
                  <td
                    key={`${test.id}-${metricRow.key}`}
                    className={`px-4 py-3 ${isBest ? "bg-success/5" : ""}`}
                  >
                    <div className="space-y-1.5">
                      {/* Absolute value */}
                      {showValues && (
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-sm tabular-nums">
                            {metricRow.format(value)}
                          </span>
                          {isBest && values.length > 1 && (
                            <Crown className="h-3 w-3 text-success" />
                          )}
                        </div>
                      )}

                      {/* Delta bar / value */}
                      {showDelta && diff != null && (
                        <>
                          {cellView === "delta" ? (
                            <DivergentBar diff={diff} isGood={diffIsGood} />
                          ) : (
                            <div
                              className={`flex items-center gap-0.5 text-[11px] tabular-nums ${
                                diffIsGood
                                  ? "text-success"
                                  : diff === 0
                                    ? "text-muted-foreground"
                                    : "text-warning"
                              }`}
                            >
                              {diff > 0 ? (
                                <TrendingUp className="h-3 w-3" />
                              ) : diff < 0 ? (
                                <TrendingDown className="h-3 w-3" />
                              ) : (
                                <Minus className="h-3 w-3" />
                              )}
                              {diff >= 0 ? "+" : ""}
                              {diff.toFixed(1)}%
                            </div>
                          )}
                        </>
                      )}

                      {/* Mini bar for values mode */}
                      {showValues && value != null && (
                        <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${
                              isBest ? "bg-success" : "bg-primary/60"
                            }`}
                            style={{ width: `${Math.max(4, barWidth)}%` }}
                          />
                        </div>
                      )}

                      {/* Baseline label in delta-only mode */}
                      {cellView === "delta" && isBaseline && (
                        <span className="text-xs text-muted-foreground">baseline</span>
                      )}
                    </div>
                  </td>
                )
              })}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function DivergentBar({ diff, isGood }: { diff: number; isGood: boolean }) {
  const clamp = Math.min(50, Math.max(-50, diff))
  const pct = Math.abs(clamp) / 50 * 50

  const barColor = isGood ? "bg-success" : "bg-warning"

  return (
    <div className="flex items-center gap-2">
      <div className="relative h-3 w-full rounded-full bg-muted/50 overflow-hidden">
        <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
        {clamp >= 0 ? (
          <div
            className={`absolute inset-y-0 left-1/2 rounded-r-full ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        ) : (
          <div
            className={`absolute inset-y-0 rounded-l-full ${barColor}`}
            style={{ width: `${pct}%`, right: "50%" }}
          />
        )}
      </div>
      <span
        className={`shrink-0 font-mono text-[11px] tabular-nums ${
          isGood ? "text-success" : "text-warning"
        }`}
      >
        {diff >= 0 ? "+" : ""}
        {diff.toFixed(1)}%
      </span>
    </div>
  )
}
