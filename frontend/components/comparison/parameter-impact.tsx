"use client"

import { ArrowUp, ArrowDown, Equal, Settings, Database, Hash, Timer, Layers } from "lucide-react"

import type { ComparisonResult, ParameterImpactSummary } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-primary" />
          Влияние параметров конфигурации
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {result.parameter_impacts.map((summary) => (
          <ImpactSummaryCard key={summary.test_id} summary={summary} />
        ))}
      </CardContent>
    </Card>
  )
}

function ImpactSummaryCard({ summary }: { summary: ParameterImpactSummary }) {
  if (summary.impacts.length === 0) {
    return null
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="outline">{summary.test_name}</Badge>
        <span className="text-sm text-muted-foreground">vs baseline «{summary.vs_baseline}»</span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {summary.impacts.map((impact) => (
          <div
            key={impact.parameter}
            className="rounded-lg border border-border bg-muted/20 p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              {PARAM_ICONS[impact.parameter] || <Settings className="h-4 w-4" />}
              <span className="font-medium text-sm">
                {PARAM_LABELS[impact.parameter] || impact.parameter}
              </span>
              <Badge variant="secondary" className="text-xs ml-auto">
                {impact.change_description}
              </Badge>
            </div>

            {impact.effects.length > 0 && (
              <div className="space-y-1 pl-6">
                {impact.effects.map((effect, idx) => {
                  const isPositive = effect.includes("рост") && !effect.includes("Latency")
                    || effect.includes("снижение") && effect.includes("Latency")
                    || effect.includes("повысилась")
                  const isNegative = effect.includes("снижение") && !effect.includes("Latency")
                    || effect.includes("рост") && effect.includes("Latency")
                    || effect.includes("снизилась")

                  return (
                    <div key={idx} className="flex items-start gap-1.5 text-sm">
                      {isPositive ? (
                        <ArrowUp className="h-3.5 w-3.5 text-green-500 shrink-0 mt-0.5" />
                      ) : isNegative ? (
                        <ArrowDown className="h-3.5 w-3.5 text-red-500 shrink-0 mt-0.5" />
                      ) : (
                        <Equal className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                      )}
                      <span className="text-muted-foreground">{effect}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {summary.summary_text && (
        <p className="text-sm text-muted-foreground border-l-2 border-primary/30 pl-3 italic">
          {summary.summary_text}
        </p>
      )}
    </div>
  )
}
