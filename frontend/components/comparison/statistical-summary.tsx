"use client"

import { AlertCircle, CheckCircle2, Sigma } from "lucide-react"

import type { ComparisonResult } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"

interface StatisticalSummaryProps {
  result: ComparisonResult
}

const COMPARISON_TYPE_LABELS: Record<ComparisonResult["comparison_type"], string> = {
  cross_database: "Сравнение СУБД",
  scalability: "Анализ масштабируемости",
  mixed: "Смешанное сравнение",
  temporal: "Временное сравнение",
}

export function StatisticalSummary({ result }: StatisticalSummaryProps) {
  const baselineTest = result.tests.find((test) => test.id === result.baseline_id)
  const significantCount = result.pairwise_comparisons.filter((item) => item.is_significant).length

  return (
    <div className="space-y-4">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sigma className="h-5 w-5 text-primary" />
            Статистический итог
          </CardTitle>
          <CardDescription>
            Baseline: {baselineTest?.name || result.baseline_id}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Тестов в сравнении</p>
            <p className="text-2xl font-semibold">{result.tests.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Попарных сравнений</p>
            <p className="text-2xl font-semibold">{result.pairwise_comparisons.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-xs text-muted-foreground">Значимых различий</p>
            <p className="text-2xl font-semibold">{significantCount}</p>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3 md:col-span-3">
            <p className="text-xs text-muted-foreground">Тип сравнения</p>
            <p className="mt-1 text-lg font-semibold">{COMPARISON_TYPE_LABELS[result.comparison_type]}</p>
          </div>
        </CardContent>
      </Card>

      {result.warnings.length > 0 && (
        <Alert className="border-amber-500/30 bg-amber-500/5">
          <AlertCircle className="h-4 w-4 text-amber-500" />
          <AlertTitle>Предупреждения анализа</AlertTitle>
          <AlertDescription>
            <div className="space-y-1">
              {result.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-3">
        {result.pairwise_comparisons.map((item) => (
          <Card key={`${item.baseline_test_id}-${item.compared_test_id}-${item.db_key}-${item.metric}`} className="bg-card border-border">
            <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  {item.is_significant ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-muted-foreground" />
                  )}
                  <p className="font-medium">
                    {item.db_key} · {formatMetricLabel(item.metric)}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">{item.interpretation}</p>
                {item.warning && <p className="text-xs text-amber-600">{item.warning}</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">p={item.p_value?.toFixed(4) ?? "N/A"}</Badge>
                <Badge variant="outline">{item.test_used || "без теста"}</Badge>
                <Badge variant={item.is_significant ? "default" : "outline"}>
                  {item.is_significant ? "значимо" : "не значимо"}
                </Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function formatMetricLabel(metric: string): string {
  switch (metric) {
    case "latency_ms":
      return "Latency"
    case "throughput":
      return "Throughput"
    case "throughput_per_thread":
      return "Throughput на поток"
    case "scaling_efficiency":
      return "Scaling efficiency"
    default:
      return metric
  }
}
