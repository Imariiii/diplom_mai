"use client"

import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  Database,
  Hash,
  Timer,
  Layers,
  Settings,
  Zap,
} from "lucide-react"

import type {
  ParameterImpactSummary,
  MetricEffect,
  ComparisonResult,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"

interface ParameterImpactProps {
  result: ComparisonResult
}

const PARAM_ICONS: Record<string, React.ReactNode> = {
  virtual_users: <Hash className="h-3.5 w-3.5" />,
  iterations: <Layers className="h-3.5 w-3.5" />,
  use_indexes: <Database className="h-3.5 w-3.5" />,
  warmup_time: <Timer className="h-3.5 w-3.5" />,
}

const METRIC_LABELS: Record<string, string> = {
  throughput: "Throughput",
  latency_mean: "Latency mean",
  latency_p99: "Latency p99",
  latency_cv: "Стабильность (CV)",
}

const METRIC_UNITS: Record<string, string> = {
  throughput: "req/s",
  latency_mean: "мс",
  latency_p99: "мс",
  latency_cv: "",
}

export function ParameterImpact({ result }: ParameterImpactProps) {
  if (!result.parameter_impacts || result.parameter_impacts.length === 0) {
    return null
  }

  return (
    <section className="space-y-3" aria-label="Влияние параметров">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Zap className="h-3.5 w-3.5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Влияние параметров</h2>
            <p className="text-xs text-muted-foreground">
              Как изменения конфигурации повлияли на результат
            </p>
          </div>
        </div>
        <Badge variant="outline" className="shrink-0 font-mono text-[11px]">
          {result.parameter_impacts.length} сравнений
        </Badge>
      </header>

      <div className="grid gap-3 xl:grid-cols-2">
        {result.parameter_impacts.map((summary) => (
          <ImpactCard
            key={summary.test_id}
            summary={summary}
            dbKeyLabels={result.db_key_labels}
          />
        ))}
      </div>
    </section>
  )
}

function ImpactCard({
  summary,
  dbKeyLabels,
}: {
  summary: ParameterImpactSummary
  dbKeyLabels?: Record<string, string>
}) {
  if (
    summary.changed_parameters.length === 0 &&
    summary.metric_effects.length === 0
  )
    return null

  const dbKeys = Array.from(
    new Set(summary.metric_effects.map((e) => e.db_key))
  )
  const metricKeys = Array.from(
    new Set(summary.metric_effects.map((e) => e.metric))
  )

  const effectMap = new Map<string, MetricEffect>()
  for (const e of summary.metric_effects) {
    effectMap.set(`${e.db_key}:${e.metric}`, e)
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4 md:p-5">
      {/* Header: test vs baseline + changed param badges */}
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-mono text-sm font-medium">{summary.test_name}</p>
        <span className="text-xs text-muted-foreground">vs</span>
        <Badge variant="outline" className="font-mono text-[11px]">
          {summary.vs_baseline}
        </Badge>
      </div>

      {/* Changed parameters as pill badges */}
      {summary.changed_parameters.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {summary.changed_parameters.map((cp) => (
            <Badge
              key={cp.parameter}
              variant="secondary"
              className="gap-1.5 font-mono text-[11px] tabular-nums"
            >
              <span className="text-muted-foreground">
                {PARAM_ICONS[cp.parameter] || <Settings className="h-3.5 w-3.5" />}
              </span>
              {cp.label}: {cp.change_description}
            </Badge>
          ))}
        </div>
      )}

      {/* Top insights */}
      {summary.top_insights.length > 0 && (
        <div className="mt-3 space-y-1">
          {summary.top_insights.map((insight, idx) => (
            <InsightRow key={idx} text={insight} />
          ))}
        </div>
      )}

      {/* Metric × DB matrix table */}
      {metricKeys.length > 0 && dbKeys.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border/60">
                <th className="pb-2 pr-3 text-left font-medium text-muted-foreground">
                  Метрика
                </th>
                {dbKeys.map((dbKey) => (
                  <th
                    key={dbKey}
                    className="pb-2 px-2 text-center font-medium text-muted-foreground"
                  >
                    {dbKeyLabels?.[dbKey] || dbKey}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricKeys.map((metric) => (
                <tr key={metric} className="border-b border-border/40 last:border-b-0">
                  <td className="py-2 pr-3 font-medium">
                    {METRIC_LABELS[metric] || metric}
                  </td>
                  {dbKeys.map((dbKey) => {
                    const effect = effectMap.get(`${dbKey}:${metric}`)
                    if (!effect) {
                      return (
                        <td key={dbKey} className="px-2 py-2 text-center text-muted-foreground">
                          —
                        </td>
                      )
                    }
                    return (
                      <td key={dbKey} className="px-2 py-2 text-center">
                        <EffectCell effect={effect} />
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function InsightRow({ text }: { text: string }) {
  const isNegative = /снизился|упал|вырос.*(latency|cv)/i.test(text)
  const Icon = isNegative ? AlertTriangle : TrendingUp

  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon
        className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${
          isNegative ? "text-warning" : "text-success"
        }`}
      />
      <span className="text-muted-foreground leading-relaxed">{text}</span>
    </div>
  )
}

function EffectCell({ effect }: { effect: MetricEffect }) {
  const unit = METRIC_UNITS[effect.metric] || ""

  const colorCls =
    effect.magnitude === "negligible"
      ? "bg-muted text-muted-foreground"
      : effect.is_improvement
        ? "bg-success/10 text-success"
        : "bg-warning/10 text-warning"

  const DirIcon =
    effect.direction === "up"
      ? TrendingUp
      : effect.direction === "down"
        ? TrendingDown
        : Minus

  const fmtVal = (v: number) =>
    unit === "req/s" ? v.toFixed(0) : unit === "мс" ? v.toFixed(2) : v.toFixed(2)

  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] tabular-nums ${colorCls}`}
      >
        <DirIcon className="h-3 w-3" />
        {effect.pct_change >= 0 ? "+" : ""}
        {effect.pct_change.toFixed(1)}%
      </span>
      <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
        {fmtVal(effect.baseline_value)} → {fmtVal(effect.compared_value)}
        {unit ? ` ${unit}` : ""}
      </span>
    </div>
  )
}
