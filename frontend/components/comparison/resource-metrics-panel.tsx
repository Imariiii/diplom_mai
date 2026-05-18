"use client"

import { Server } from "lucide-react"
import type { ComparisonResult } from "@/lib/api"
import { getCacheHitDisplay } from "@/lib/dbms-cache-metrics"

function resolveDbKeyLabel(dbKey: string, labels?: Record<string, string>): string {
  return labels?.[dbKey] || dbKey
}

interface ResourceMetricsPanelProps {
  result: ComparisonResult
}

export function ResourceMetricsPanel({ result }: ResourceMetricsPanelProps) {
  const resourceMetrics = result.resource_metrics
  if (!resourceMetrics || Object.keys(resourceMetrics).length === 0) {
    return null
  }

  const testIds = Object.keys(resourceMetrics)
  const dbKeys = new Set<string>()
  for (const tid of testIds) {
    Object.keys(resourceMetrics[tid] || {}).forEach((k) => dbKeys.add(k))
  }
  const labels = result.db_key_labels

  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex items-start gap-2.5 border-b border-border p-4">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Server className="h-3.5 w-3.5" />
        </div>
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Ресурсы хоста и СУБД</h2>
          <p className="text-xs text-muted-foreground">
            Снимок в конце прогона: CPU, RAM, кэш, блокировки
          </p>
        </div>
      </div>
      <div className="overflow-x-auto p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 text-left font-medium">СУБД</th>
              {testIds.map((tid) => (
                <th key={tid} className="px-3 py-2 text-left font-medium">
                  {tid.slice(0, 8)}…
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from(dbKeys).map((dbKey) => (
              <tr key={dbKey} className="border-b border-border/40">
                <td className="px-3 py-2 font-medium">{resolveDbKeyLabel(dbKey, labels)}</td>
                {testIds.map((tid) => {
                  const rm = resourceMetrics[tid]?.[dbKey]
                  if (!rm) {
                    return (
                      <td key={tid} className="px-3 py-2 text-muted-foreground">
                        —
                      </td>
                    )
                  }
                  const cache = getCacheHitDisplay({
                    cacheHitRatio: rm.cache_hit_ratio ?? rm.buffer_pool_hit_ratio,
                    cacheHitRatioStatus: "ok",
                  })
                  return (
                    <td key={tid} className="px-3 py-2 font-mono text-xs space-y-0.5">
                      <div>CPU: {rm.cpu_usage?.toFixed(1) ?? "—"}%</div>
                      <div>RAM: {rm.memory_usage_percent?.toFixed(1) ?? "—"}%</div>
                      <div>Кэш: {cache.valueText}</div>
                      <div>Блокировки: {rm.lock_waits ?? "—"}</div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
