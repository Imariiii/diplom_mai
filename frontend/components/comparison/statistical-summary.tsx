"use client"

import { useState } from "react"
import { AlertCircle, CheckCircle2, Sigma, Filter } from "lucide-react"

import type { ComparisonResult, PairwiseComparison } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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

const EFFECT_COLORS: Record<string, string> = {
  large: "bg-red-500/10 text-red-600 border-red-500/20",
  medium: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  small: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  negligible: "bg-muted text-muted-foreground border-border",
}

const EFFECT_LABELS: Record<string, string> = {
  large: "большой",
  medium: "средний",
  small: "малый",
  negligible: "пренебрежимый",
}

export function StatisticalSummary({ result }: StatisticalSummaryProps) {
  const [showOnlySignificant, setShowOnlySignificant] = useState(false)
  const [isOpen, setIsOpen] = useState(true)

  const grouped = groupByMetric(result.pairwise_comparisons)
  const filteredGroups: Record<string, PairwiseComparison[]> = showOnlySignificant
    ? Object.fromEntries(
        Object.entries(grouped)
          .map(([metric, items]) => [metric, items.filter((p) => p.is_significant)] as const)
          .filter(([, items]) => items.length > 0)
      )
    : grouped

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CollapsibleTrigger asChild>
              <button className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <Sigma className="h-5 w-5 text-primary" />
                <CardTitle>Статистические тесты</CardTitle>
              </button>
            </CollapsibleTrigger>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Switch
                  id="sig-filter"
                  checked={showOnlySignificant}
                  onCheckedChange={setShowOnlySignificant}
                />
                <Label htmlFor="sig-filter" className="text-xs text-muted-foreground">
                  Только значимые
                </Label>
              </div>
            </div>
          </div>
          <CardDescription>
            Попарные сравнения с baseline: p-value, размер эффекта (Cohen&apos;s d), доверительные интервалы
          </CardDescription>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="space-y-6">
            {Object.entries(filteredGroups).map(([metric, items]) => (
              <div key={metric} className="space-y-2">
                <h3 className="font-medium text-sm flex items-center gap-2">
                  {METRIC_LABELS[metric] || metric}
                  <Badge variant="outline" className="text-xs">{items.length}</Badge>
                </h3>
                <div className="grid gap-2">
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

            {Object.keys(filteredGroups).length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                {showOnlySignificant
                  ? "Статистически значимых различий не обнаружено"
                  : "Попарные сравнения отсутствуют"}
              </p>
            )}
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}

function ComparisonCard({ item, result }: { item: PairwiseComparison; result: ComparisonResult }) {
  const baselineName =
    result.tests.find((t) => t.id === item.baseline_test_id)?.name || item.baseline_test_id
  const comparedName =
    result.tests.find((t) => t.id === item.compared_test_id)?.name || item.compared_test_id

  const effectColor = item.effect_size_label
    ? EFFECT_COLORS[item.effect_size_label] || EFFECT_COLORS.negligible
    : ""

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="space-y-1 min-w-0">
        <div className="flex items-center gap-2">
          {item.is_significant ? (
            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 text-muted-foreground shrink-0" />
          )}
          <span className="font-medium text-sm truncate">
            {resolveDbKeyLabel(item.db_key, result.db_key_labels)}
          </span>
          <span className="text-xs text-muted-foreground">
            {baselineName} vs {comparedName}
          </span>
        </div>
        <p className="text-sm text-muted-foreground pl-6">{item.interpretation}</p>

        {item.ci_lower != null && item.ci_upper != null && (
          <p className="text-xs text-muted-foreground pl-6">
            95% CI: [{item.ci_lower.toFixed(2)}, {item.ci_upper.toFixed(2)}]
            {item.metric === "latency_ms" ? " мс" : " req/s"}
          </p>
        )}

        {item.warning && (
          <p className="text-xs text-amber-600 pl-6">{item.warning}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 pl-6 lg:pl-0 shrink-0">
        {item.effect_size != null && item.effect_size_label && (
          <Badge variant="outline" className={`text-xs ${effectColor}`}>
            d={Math.abs(item.effect_size).toFixed(2)} ({EFFECT_LABELS[item.effect_size_label] || item.effect_size_label})
          </Badge>
        )}
        <Badge variant="outline" className="text-xs">
          p={item.p_value?.toFixed(4) ?? "N/A"}
        </Badge>
        <Badge variant="outline" className="text-xs">
          {item.test_used || "без теста"}
        </Badge>
        <Badge variant={item.is_significant ? "default" : "outline"} className="text-xs">
          {item.is_significant ? "значимо" : "не значимо"}
        </Badge>
      </div>
    </div>
  )
}

function groupByMetric(comparisons: PairwiseComparison[]): Record<string, PairwiseComparison[]> {
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
