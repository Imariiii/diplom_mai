"use client"

import type { ComparisonResult, MetricStatsBundle, NormalizedMetrics } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface ComparisonTableProps {
  result: ComparisonResult
  useNormalized?: boolean
}

interface MetricRow {
  key: string
  label: string
  better: "lower" | "higher"
  accessor: (bundle: MetricStatsBundle | undefined, normalized: NormalizedMetrics | undefined) => number | null | undefined
  format: (value: number | null | undefined) => string
}

const RAW_METRIC_ROWS: MetricRow[] = [
  {
    key: "latency_mean",
    label: "Latency mean",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.mean,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_median",
    label: "Latency median",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.median,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_p95",
    label: "Latency p95",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.p95,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_p99",
    label: "Latency p99",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.p99,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_min",
    label: "Latency min",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.min,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_max",
    label: "Latency max",
    better: "lower",
    accessor: (bundle) => bundle?.latency_ms?.max,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "throughput_mean",
    label: "Throughput mean",
    better: "higher",
    accessor: (bundle) => bundle?.throughput?.mean,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "throughput_median",
    label: "Throughput median",
    better: "higher",
    accessor: (bundle) => bundle?.throughput?.median,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "throughput_p95",
    label: "Throughput p95",
    better: "higher",
    accessor: (bundle) => bundle?.throughput?.p95,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "throughput_p99",
    label: "Throughput p99",
    better: "higher",
    accessor: (bundle) => bundle?.throughput?.p99,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "error_rate",
    label: "Error rate",
    better: "lower",
    accessor: (bundle) => bundle?.error_rate,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)}%`,
  },
  {
    key: "duration",
    label: "Общее время",
    better: "lower",
    accessor: (bundle) => bundle?.total_duration_sec,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} с`,
  },
]

const NORMALIZED_METRIC_ROWS: MetricRow[] = [
  {
    key: "throughput_abs",
    label: "Throughput absolute",
    better: "higher",
    accessor: (_, normalized) => normalized?.throughput_abs,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "throughput_per_thread",
    label: "Throughput на поток",
    better: "higher",
    accessor: (_, normalized) => normalized?.throughput_per_thread,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s/thread`,
  },
  {
    key: "throughput_per_second",
    label: "Throughput по duration",
    better: "higher",
    accessor: (_, normalized) => normalized?.throughput_per_second,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} req/s`,
  },
  {
    key: "scaling_efficiency",
    label: "Scaling efficiency",
    better: "higher",
    accessor: (_, normalized) => normalized?.scaling_efficiency,
    format: (value) => value == null ? "N/A" : `${(value * 100).toFixed(1)}%`,
  },
  {
    key: "latency_mean_abs",
    label: "Latency absolute",
    better: "lower",
    accessor: (_, normalized) => normalized?.latency_mean_abs,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} мс`,
  },
  {
    key: "latency_per_thread",
    label: "Latency на поток",
    better: "lower",
    accessor: (_, normalized) => normalized?.latency_per_thread,
    format: (value) => value == null ? "N/A" : `${value.toFixed(4)} мс/thread`,
  },
  {
    key: "threads",
    label: "Потоки",
    better: "higher",
    accessor: (_, normalized) => normalized?.threads,
    format: (value) => value == null ? "N/A" : `${value.toFixed(0)}`,
  },
  {
    key: "duration_seconds",
    label: "Длительность",
    better: "lower",
    accessor: (_, normalized) => normalized?.duration_seconds,
    format: (value) => value == null ? "N/A" : `${value.toFixed(2)} с`,
  },
]

export function ComparisonTable({ result, useNormalized = false }: ComparisonTableProps) {
  const dbKeys = Array.from(
    new Set(
      Object.values(result.descriptive_stats).flatMap((bundleMap) => Object.keys(bundleMap))
    )
  )

  const baselineId = result.baseline_id
  const metricRows = useNormalized ? NORMALIZED_METRIC_ROWS : RAW_METRIC_ROWS

  const getBestValue = (metricRow: MetricRow, dbKey: string) => {
    const values = result.tests
      .map((test) => metricRow.accessor(result.descriptive_stats[test.id]?.[dbKey], result.normalized_metrics[test.id]?.[dbKey]))
      .filter((value): value is number => typeof value === "number")

    if (values.length === 0) return null
    return metricRow.better === "lower" ? Math.min(...values) : Math.max(...values)
  }

  return (
    <div className="space-y-6">
      {dbKeys.map((dbKey) => (
        <Card key={dbKey} className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-4">
              <span>{dbKey}</span>
              <Badge variant="outline">Baseline: {result.tests.find((test) => test.id === baselineId)?.name || baselineId}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Метрика</TableHead>
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
                      <TableCell className="font-medium">{metricRow.label}</TableCell>
                      {result.tests.map((test) => {
                        const bundle = result.descriptive_stats[test.id]?.[dbKey]
                        const normalized = result.normalized_metrics[test.id]?.[dbKey]
                        const value = metricRow.accessor(bundle, normalized)
                        const isBest = bestValue != null && value === bestValue
                        const diff = baselineValue == null || baselineValue === 0 || value == null
                          ? null
                          : ((value - baselineValue) / baselineValue) * 100

                        return (
                          <TableCell key={`${test.id}-${metricRow.key}`} className={isBest ? "bg-green-500/5" : undefined}>
                            <div className="space-y-1">
                              <p className="font-mono">{metricRow.format(value)}</p>
                              {test.id !== baselineId && (
                                <p className="text-xs text-muted-foreground">
                                  Δ {diff == null ? "N/A" : `${diff >= 0 ? "+" : ""}${diff.toFixed(1)}%`}
                                </p>
                              )}
                              {!useNormalized && bundle?.source && (
                                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{bundle.source}</p>
                              )}
                              {useNormalized && normalized?.normalization_warning && (
                                <p className="text-xs text-amber-600">{normalized.normalization_warning}</p>
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
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
