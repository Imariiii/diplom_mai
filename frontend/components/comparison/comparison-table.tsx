"use client"

import { useState } from "react"

import type { ComparisonResult, MetricStatsBundle, NormalizedMetrics } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

interface ComparisonTableProps {
  result: ComparisonResult
  useNormalized?: boolean
}

interface MetricRow {
  key: string
  label: string
  better: "lower" | "higher"
  isCore: boolean
  accessor: (bundle: MetricStatsBundle | undefined, normalized: NormalizedMetrics | undefined) => number | null | undefined
  format: (value: number | null | undefined) => string
}

const RAW_METRIC_ROWS: MetricRow[] = [
  {
    key: "latency_mean",
    label: "Latency mean",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.latency_ms?.mean,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_median",
    label: "Latency median",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.latency_ms?.median,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_p95",
    label: "Latency p95",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.latency_ms?.p95,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_p99",
    label: "Latency p99",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.latency_ms?.p99,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_cv",
    label: "Latency CV",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.latency_ms?.cv,
    format: (v) => v == null ? "N/A" : `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "throughput_mean",
    label: "Throughput mean",
    better: "higher",
    isCore: true,
    accessor: (bundle) => bundle?.throughput?.mean,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} req/s`,
  },
  {
    key: "error_rate",
    label: "Error rate",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.error_rate,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)}%`,
  },
  {
    key: "duration",
    label: "Общее время",
    better: "lower",
    isCore: true,
    accessor: (bundle) => bundle?.total_duration_sec,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} с`,
  },
  {
    key: "latency_min",
    label: "Latency min",
    better: "lower",
    isCore: false,
    accessor: (bundle) => bundle?.latency_ms?.min,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_max",
    label: "Latency max",
    better: "lower",
    isCore: false,
    accessor: (bundle) => bundle?.latency_ms?.max,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "latency_iqr",
    label: "Latency IQR",
    better: "lower",
    isCore: false,
    accessor: (bundle) => bundle?.latency_ms?.iqr,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "throughput_median",
    label: "Throughput median",
    better: "higher",
    isCore: false,
    accessor: (bundle) => bundle?.throughput?.median,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} req/s`,
  },
  {
    key: "throughput_cv",
    label: "Throughput CV",
    better: "lower",
    isCore: false,
    accessor: (bundle) => bundle?.throughput?.cv,
    format: (v) => v == null ? "N/A" : `${(v * 100).toFixed(1)}%`,
  },
]

const NORMALIZED_METRIC_ROWS: MetricRow[] = [
  {
    key: "throughput_abs",
    label: "Throughput absolute",
    better: "higher",
    isCore: true,
    accessor: (_, n) => n?.throughput_abs,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} req/s`,
  },
  {
    key: "throughput_per_thread",
    label: "Throughput на поток",
    better: "higher",
    isCore: true,
    accessor: (_, n) => n?.throughput_per_thread,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} req/s/thread`,
  },
  {
    key: "scaling_efficiency",
    label: "Scaling efficiency",
    better: "higher",
    isCore: true,
    accessor: (_, n) => n?.scaling_efficiency,
    format: (v) => v == null ? "N/A" : `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "latency_mean_abs",
    label: "Latency absolute",
    better: "lower",
    isCore: true,
    accessor: (_, n) => n?.latency_mean_abs,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} мс`,
  },
  {
    key: "threads",
    label: "Потоки",
    better: "higher",
    isCore: true,
    accessor: (_, n) => n?.threads,
    format: (v) => v == null ? "N/A" : `${v.toFixed(0)}`,
  },
  {
    key: "duration_seconds",
    label: "Длительность",
    better: "lower",
    isCore: true,
    accessor: (_, n) => n?.duration_seconds,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} с`,
  },
  {
    key: "throughput_per_second",
    label: "Throughput по duration",
    better: "higher",
    isCore: false,
    accessor: (_, n) => n?.throughput_per_second,
    format: (v) => v == null ? "N/A" : `${v.toFixed(2)} req/s`,
  },
  {
    key: "latency_per_thread",
    label: "Latency на поток",
    better: "lower",
    isCore: false,
    accessor: (_, n) => n?.latency_per_thread,
    format: (v) => v == null ? "N/A" : `${v.toFixed(4)} мс/thread`,
  },
]

export function ComparisonTable({ result, useNormalized = false }: ComparisonTableProps) {
  const [showExtended, setShowExtended] = useState(false)
  const [isOpen, setIsOpen] = useState(true)

  const dbKeys = Array.from(
    new Set(
      Object.values(result.descriptive_stats).flatMap((bm) => Object.keys(bm))
    )
  )

  const baselineId = result.baseline_id
  const allMetricRows = useNormalized ? NORMALIZED_METRIC_ROWS : RAW_METRIC_ROWS
  const metricRows = showExtended ? allMetricRows : allMetricRows.filter((r) => r.isCore)
  const hasExtended = allMetricRows.some((r) => !r.isCore)

  const getBestValue = (metricRow: MetricRow, dbKey: string) => {
    const values = result.tests
      .map((test) => metricRow.accessor(
        result.descriptive_stats[test.id]?.[dbKey],
        result.normalized_metrics[test.id]?.[dbKey]
      ))
      .filter((v): v is number => typeof v === "number")
    if (values.length === 0) return null
    return metricRow.better === "lower" ? Math.min(...values) : Math.max(...values)
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CollapsibleTrigger asChild>
              <button className="hover:opacity-80 transition-opacity">
                <CardTitle>Детальные метрики</CardTitle>
              </button>
            </CollapsibleTrigger>
            {hasExtended && (
              <div className="flex items-center gap-2">
                <Switch id="extended-metrics" checked={showExtended} onCheckedChange={setShowExtended} />
                <Label htmlFor="extended-metrics" className="text-xs text-muted-foreground">
                  Все метрики
                </Label>
              </div>
            )}
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="space-y-6 p-0">
            {dbKeys.map((dbKey) => (
              <div key={dbKey}>
                <div className="flex items-center justify-between gap-4 px-6 pb-2">
                  <span className="font-medium">{resolveDbKeyLabel(dbKey, result.db_key_labels)}</span>
                  <Badge variant="outline" className="text-xs">
                    Baseline: {result.tests.find((t) => t.id === baselineId)?.name || baselineId}
                  </Badge>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">Метрика</TableHead>
                      {result.tests.map((test) => (
                        <TableHead key={test.id}>{test.name}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {metricRows.map((metricRow) => {
                      const bestValue = getBestValue(metricRow, dbKey)
                      const baselineBundle = result.descriptive_stats[baselineId]?.[dbKey]
                      const baselineNormalized = result.normalized_metrics[baselineId]?.[dbKey]
                      const baselineValue = metricRow.accessor(baselineBundle, baselineNormalized)

                      return (
                        <TableRow key={`${dbKey}-${metricRow.key}`}>
                          <TableCell className="font-medium text-sm">{metricRow.label}</TableCell>
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

                            return (
                              <TableCell
                                key={`${test.id}-${metricRow.key}`}
                                className={isBest ? "bg-green-500/5" : undefined}
                              >
                                <div className="space-y-0.5">
                                  <p className="font-mono text-sm">{metricRow.format(value)}</p>
                                  {test.id !== baselineId && diff != null && (
                                    <p className={`text-xs ${diffIsGood ? "text-green-600" : diff === 0 ? "text-muted-foreground" : "text-red-500"}`}>
                                      Δ {diff >= 0 ? "+" : ""}{diff.toFixed(1)}%
                                    </p>
                                  )}
                                </div>
                              </TableCell>
                            )
                          })}
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
