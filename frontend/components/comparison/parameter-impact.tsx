"use client"

import {
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Database,
  Hash,
  Timer,
  Layers,
  Settings,
  Zap,
} from "lucide-react"

import type { ParameterImpactSummary, ComparisonResult } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

interface ParameterImpactProps {
  result: ComparisonResult
}

const PARAM_ICONS: Record<string, React.ReactNode> = {
  virtual_users: <Hash className="h-4 w-4" />,
  iterations: <Layers className="h-4 w-4" />,
  use_indexes: <Database className="h-4 w-4" />,
  warmup_time: <Timer className="h-4 w-4" />,
}

const PARAM_LABELS: Record<string, string> = {
  virtual_users: "Виртуальные пользователи",
  iterations: "Итерации",
  use_indexes: "Индексы",
  warmup_time: "Прогрев",
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
          <ImpactCard key={summary.test_id} summary={summary} />
        ))}
      </div>
    </section>
  )
}

function ImpactCard({ summary }: { summary: ParameterImpactSummary }) {
  if (summary.impacts.length === 0) return null

  return (
    <div className="rounded-xl border border-border bg-card p-4 md:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-mono text-sm font-medium">{summary.test_name}</p>
        <span className="text-xs text-muted-foreground">vs</span>
        <Badge variant="outline" className="font-mono text-[11px]">
          {summary.vs_baseline}
        </Badge>
      </div>

      <div className="mt-4 space-y-3">
        {summary.impacts.map((impact) => (
          <div
            key={impact.parameter}
            className="rounded-lg border border-border/60 bg-muted/30 p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-muted-foreground">
                  {PARAM_ICONS[impact.parameter] || <Settings className="h-4 w-4" />}
                </span>
                <p className="truncate text-sm font-medium">
                  {PARAM_LABELS[impact.parameter] || impact.parameter}
                </p>
              </div>
              <Badge
                variant="secondary"
                className="shrink-0 font-mono text-[11px] tabular-nums"
              >
                {impact.change_description}
              </Badge>
            </div>

            {impact.effects.length > 0 && (
              <ul className="mt-2.5 space-y-1 border-l-2 border-border/60 pl-3">
                {impact.effects.map((effect, idx) => (
                  <EffectItem key={idx} effect={effect} />
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {summary.summary_text && (
        <div className="mt-4 rounded-lg bg-primary/5 p-3">
          <p className="text-sm italic leading-relaxed text-foreground/80">
            {summary.summary_text}
          </p>
        </div>
      )}
    </div>
  )
}

function EffectItem({ effect }: { effect: string }) {
  const isLatencyMetric = /latency/i.test(effect)
  const isGrowth = /рост|повысилась|увелич/i.test(effect)
  const isDrop = /снижение|снизилась|упал/i.test(effect)

  // For latency: growth is bad, drop is good
  // For throughput/efficiency: growth is good, drop is bad
  const isGood = isLatencyMetric
    ? isDrop || /повысилась/i.test(effect)
    : isGrowth || /повысилась/i.test(effect)
  const isBad = isLatencyMetric ? isGrowth : isDrop

  return (
    <li className="flex items-start gap-2 text-sm leading-relaxed">
      {isGood ? (
        <ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
      ) : isBad ? (
        <ArrowDownRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
      ) : (
        <Minus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      )}
      <span className="text-muted-foreground">{effect}</span>
    </li>
  )
}
