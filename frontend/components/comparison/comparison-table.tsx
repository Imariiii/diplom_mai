"use client"

import { useMemo, useState } from "react"
import { Crown, TrendingDown, TrendingUp, Minus, Table2 } from "lucide-react"

import {
  type ComparisonResult,
  type MetricStatsBundle,
  isPerTestResult,
  isSeriesResult,
} from "@/lib/api"
import {
  buildComparisonMetricRows,
  resolveComparisonWorkloadMode,
} from "@/lib/throughput-metrics"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

interface ComparisonTableProps {
  result: ComparisonResult
}

type CellView = "values" | "delta" | "both"

interface MetricRow {
  key: string
  label: string
  better: "lower" | "higher"
  isCore: boolean
  unit: string
  accessor: (bundle: MetricStatsBundle | undefined) => number | null | undefined
  format: (value: number | null | undefined) => string
}

export function ComparisonTable({ result }: ComparisonTableProps) {
  if (isPerTestResult(result)) return <PerTestTable result={result} />
  if (isSeriesResult(result)) return <SeriesTable result={result} />
  return null
}

// ═══════════════════════════════════════════════════════════════════════════
// Per-test: columns = db_keys, rows = metrics
// ═══════════════════════════════════════════════════════════════════════════

function PerTestTable({
  result,
}: {
  result: Extract<ComparisonResult, { analysis_mode: "per_test" }>
}) {
  const [showExtended, setShowExtended] = useState(false)
  const workloadMode = resolveComparisonWorkloadMode(result)
  const allMetricRows = useMemo(
    () => buildComparisonMetricRows(workloadMode),
    [workloadMode],
  )

  const dbKeys = useMemo(() => Object.keys(result.descriptive_stats), [result])
  const metricRows = showExtended ? allMetricRows : allMetricRows.filter((r) => r.isCore)
  const hasExtended = allMetricRows.some((r) => !r.isCore)

  const firstDbKey = dbKeys[0]

  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Table2 className="h-3.5 w-3.5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Детальные метрики по СУБД</h2>
            <p className="text-xs text-muted-foreground">
              Построчное сравнение · зелёным отмечено лучшее значение
            </p>
          </div>
        </div>
        {hasExtended && (
          <div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2 py-1">
            <Label htmlFor="extended-metrics" className="cursor-pointer text-xs text-muted-foreground">
              Все метрики
            </Label>
            <Switch id="extended-metrics" checked={showExtended} onCheckedChange={setShowExtended} />
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2.5 text-left font-medium">Метрика</th>
              {dbKeys.map((dbKey) => (
                <th key={dbKey} className="px-4 py-2.5 text-left font-medium">
                  {resolveDbKeyLabel(dbKey, result.db_key_labels)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((metricRow) => {
              const values = dbKeys
                .map((dbKey) => metricRow.accessor(result.descriptive_stats[dbKey]))
                .filter((v): v is number => typeof v === "number")
              const bestValue =
                values.length === 0
                  ? null
                  : metricRow.better === "lower"
                    ? Math.min(...values)
                    : Math.max(...values)
              const baselineValue = firstDbKey ? metricRow.accessor(result.descriptive_stats[firstDbKey]) : null
              const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1)

              return (
                <tr key={metricRow.key} className="border-b border-border/60 last:border-b-0 hover:bg-muted/20">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{metricRow.label}</span>
                      <Badge variant="outline" className="h-4 px-1 font-mono text-[9px] uppercase">
                        {metricRow.better === "lower" ? "↓ меньше" : "↑ больше"}
                      </Badge>
                    </div>
                  </td>
                  {dbKeys.map((dbKey, idx) => {
                    const value = metricRow.accessor(result.descriptive_stats[dbKey])
                    const isBest = bestValue != null && value === bestValue
                    const diff = baselineValue == null || baselineValue === 0 || value == null || idx === 0
                      ? null
                      : ((value - baselineValue) / baselineValue) * 100
                    const diffIsGood = diff != null && (
                      (metricRow.better === "lower" && diff < 0) ||
                      (metricRow.better === "higher" && diff > 0)
                    )
                    const barWidth = value == null ? 0 : Math.min(100, (Math.abs(value) / maxAbs) * 100)

                    return (
                      <td key={dbKey} className={`px-4 py-3 ${isBest ? "bg-success/5" : ""}`}>
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-sm tabular-nums">{metricRow.format(value)}</span>
                            {isBest && values.length > 1 && <Crown className="h-3 w-3 text-success" />}
                          </div>
                          {idx > 0 && diff != null && (
                            <div className={`flex items-center gap-0.5 text-[11px] tabular-nums ${
                              diffIsGood ? "text-success" : diff === 0 ? "text-muted-foreground" : "text-warning"
                            }`}>
                              {diff > 0 ? <TrendingUp className="h-3 w-3" /> : diff < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                              {diff >= 0 ? "+" : ""}{diff.toFixed(1)}%
                            </div>
                          )}
                          {value != null && (
                            <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                              <div className={`h-full rounded-full ${isBest ? "bg-success" : "bg-primary/60"}`} style={{ width: `${Math.max(4, barWidth)}%` }} />
                            </div>
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
      </div>
    </section>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Series: columns = tests (load levels), rows = metrics per db
// ═══════════════════════════════════════════════════════════════════════════

function SeriesTable({
  result,
}: {
  result: Extract<ComparisonResult, { analysis_mode: "series" }>
}) {
  const [showExtended, setShowExtended] = useState(false)
  const [cellView, setCellView] = useState<CellView>("both")
  const workloadMode = resolveComparisonWorkloadMode(result)
  const allMetricRows = useMemo(
    () => buildComparisonMetricRows(workloadMode),
    [workloadMode],
  )

  const dbKeys = useMemo(() => Object.keys(result.per_db), [result])
  const [activeDb, setActiveDb] = useState(dbKeys[0] ?? "")

  const metricRows = showExtended ? allMetricRows : allMetricRows.filter((r) => r.isCore)
  const hasExtended = allMetricRows.some((r) => !r.isCore)

  const levelIds = useMemo(
    () => result.load_levels.map((l) => l.level_id),
    [result]
  )
  const levelLabels = useMemo(
    () => Object.fromEntries(result.load_levels.map((l) => [l.level_id, l.label])),
    [result]
  )

  const statsByLevel = activeDb ? result.per_db[activeDb]?.descriptive_stats_by_level ?? {} : {}
  const baselineLevelId = levelIds[0]

  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Table2 className="h-3.5 w-3.5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Метрики по уровням нагрузки</h2>
            <p className="text-xs text-muted-foreground">
              Зелёным — лучшее значение среди уровней; Δ% — относительно базового уровня
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {baselineLevelId && (
            <Badge variant="outline" className="gap-1 font-mono text-[11px]">
              <Crown className="h-3 w-3" />
              Базовый: {levelLabels[baselineLevelId]}
            </Badge>
          )}
          {hasExtended && (
            <div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 px-2 py-1">
              <Label htmlFor="ext-m" className="cursor-pointer text-xs text-muted-foreground">Все метрики</Label>
              <Switch id="ext-m" checked={showExtended} onCheckedChange={setShowExtended} />
            </div>
          )}
        </div>
      </div>

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
              <TabsTrigger value="values" className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50">Значения</TabsTrigger>
              <TabsTrigger value="delta" className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50">Δ%</TabsTrigger>
              <TabsTrigger value="both" className="h-8 rounded-md border border-transparent px-3 text-xs data-[state=active]:border-border data-[state=active]:bg-muted/50">Оба</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2.5 text-left font-medium">Метрика</th>
              {levelIds.map((lid) => (
                <th key={lid} className="px-4 py-2.5 text-left font-medium">
                  <div className="flex items-center gap-1.5">
                    {levelLabels[lid] ?? lid}
                    {lid === baselineLevelId && <Crown className="h-3 w-3 text-primary" />}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((metricRow) => {
              const values = levelIds
                .map((lid) => metricRow.accessor(statsByLevel[lid]))
                .filter((v): v is number => typeof v === "number")
              const bestValue = values.length === 0
                ? null
                : metricRow.better === "lower"
                  ? Math.min(...values)
                  : Math.max(...values)
              const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1)
              const baselineValue = baselineLevelId
                ? metricRow.accessor(statsByLevel[baselineLevelId])
                : null

              return (
                <tr key={metricRow.key} className="border-b border-border/60 last:border-b-0 hover:bg-muted/20">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{metricRow.label}</span>
                      <Badge variant="outline" className="h-4 px-1 font-mono text-[9px] uppercase">
                        {metricRow.better === "lower" ? "↓ меньше" : "↑ больше"}
                      </Badge>
                    </div>
                  </td>
                  {levelIds.map((lid) => {
                    const value = metricRow.accessor(statsByLevel[lid])
                    const isBest = bestValue != null && value === bestValue
                    const isBaseline = lid === baselineLevelId
                    const diff = baselineValue == null || baselineValue === 0 || value == null
                      ? null
                      : ((value - baselineValue) / baselineValue) * 100
                    const diffIsGood = diff != null && (
                      (metricRow.better === "lower" && diff < 0) ||
                      (metricRow.better === "higher" && diff > 0)
                    )
                    const barWidth = value == null ? 0 : Math.min(100, (Math.abs(value) / maxAbs) * 100)
                    const showValues = cellView === "values" || cellView === "both"
                    const showDelta = (cellView === "delta" || cellView === "both") && !isBaseline

                    return (
                      <td key={lid} className={`px-4 py-3 ${isBest ? "bg-success/5" : ""}`}>
                        <div className="space-y-1.5">
                          {showValues && (
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-sm tabular-nums">{metricRow.format(value)}</span>
                              {isBest && values.length > 1 && <Crown className="h-3 w-3 text-success" />}
                            </div>
                          )}
                          {showDelta && diff != null && (
                            <div className={`flex items-center gap-0.5 text-[11px] tabular-nums ${
                              diffIsGood ? "text-success" : diff === 0 ? "text-muted-foreground" : "text-warning"
                            }`}>
                              {diff > 0 ? <TrendingUp className="h-3 w-3" /> : diff < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                              {diff >= 0 ? "+" : ""}{diff.toFixed(1)}%
                            </div>
                          )}
                          {showValues && value != null && (
                            <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                              <div className={`h-full rounded-full ${isBest ? "bg-success" : "bg-primary/60"}`} style={{ width: `${Math.max(4, barWidth)}%` }} />
                            </div>
                          )}
                          {cellView === "delta" && isBaseline && (
                            <span className="text-xs text-muted-foreground">базовый</span>
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
      </div>
    </section>
  )
}
