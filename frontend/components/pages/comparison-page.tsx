"use client"

import { useEffect, useState, startTransition } from "react"
import { ChevronLeft, Download, Loader2, Scale } from "lucide-react"

import { analyzeComparison, type AnalysisReportConfig, type ComparisonResult } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { ComparisonTable } from "@/components/comparison/comparison-table"
import { ComparisonCharts } from "@/components/comparison/comparison-charts"
import { StatisticalSummary } from "@/components/comparison/statistical-summary"
import { AnalysisReport } from "@/components/comparison/analysis-report"

export function ComparisonPage() {
  const {
    comparisonTestIds,
    comparisonBaselineId,
    setCurrentPage,
  } = useAppStore()

  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reportConfig, setReportConfig] = useState<AnalysisReportConfig>({
    include_verdict: true,
    include_patterns: true,
    include_recommendations: true,
    include_hypotheses: true,
  })
  const [useNormalizedView, setUseNormalizedView] = useState(true)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      if (comparisonTestIds.length < 2) {
        setError("Выберите минимум два теста для сравнения на странице истории")
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const response = await analyzeComparison({
          test_ids: comparisonTestIds,
          baseline_id: comparisonBaselineId || comparisonTestIds[0],
          report_config: reportConfig,
        })

        if (!cancelled) {
          startTransition(() => {
            setResult(response)
          })
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Ошибка анализа сравнения")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    run()

    return () => {
      cancelled = true
    }
  }, [comparisonTestIds, comparisonBaselineId, reportConfig])

  const toggleReportConfig = (key: keyof AnalysisReportConfig, checked: boolean) => {
    setReportConfig((current) => ({
      ...current,
      [key]: checked,
    }))
  }

  const exportJson = () => {
    if (!result) return

    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `comparison-${result.baseline_id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const supportsNormalizedView = Boolean(
    result && (result.comparison_type === "scalability" || result.comparison_type === "mixed")
  )

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="p-6 space-y-4">
        <Button variant="ghost" onClick={() => setCurrentPage("history")}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Назад к истории
        </Button>
        <Alert variant="destructive">
          <AlertTitle>Не удалось загрузить сравнение</AlertTitle>
          <AlertDescription>{error || "Данные анализа отсутствуют"}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Scale className="h-6 w-6 text-primary" />
            Сравнение тестов
          </h1>
          <p className="text-muted-foreground">Метрики, статистическая значимость и графики по выбранным прогонам</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setCurrentPage("history")}>
            <ChevronLeft className="mr-2 h-4 w-4" />
            История
          </Button>
          <Button onClick={exportJson}>
            <Download className="mr-2 h-4 w-4" />
            Экспорт JSON
          </Button>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Выбранные тесты</CardTitle>
          <CardDescription>{result.tests.map((test) => test.name).join(" · ")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{getComparisonTypeLabel(result.comparison_type)}</Badge>
            {supportsNormalizedView && (
              <Badge variant="outline">Нормализация доступна</Badge>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {result.tests.map((test) => (
            <div key={test.id} className="rounded-lg border border-border bg-muted/30 p-4">
              <p className="font-medium">{test.name}</p>
              <p className="text-xs text-muted-foreground">{test.id}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Сценарий: {String(test.config?.scenario || "-")}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Потоки: {String(test.config?.virtual_users || test.config?.threads || "-")}
              </p>
            </div>
          ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Конфигурация отчёта</CardTitle>
          <CardDescription>Управление rule-based секциями аналитического отчёта</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label htmlFor="report-verdict">Вердикт</Label>
            <Switch
              id="report-verdict"
              checked={reportConfig.include_verdict}
              onCheckedChange={(checked) => toggleReportConfig("include_verdict", checked)}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label htmlFor="report-patterns">Паттерны</Label>
            <Switch
              id="report-patterns"
              checked={reportConfig.include_patterns}
              onCheckedChange={(checked) => toggleReportConfig("include_patterns", checked)}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label htmlFor="report-recommendations">Рекомендации</Label>
            <Switch
              id="report-recommendations"
              checked={reportConfig.include_recommendations}
              onCheckedChange={(checked) => toggleReportConfig("include_recommendations", checked)}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <Label htmlFor="report-hypotheses">Гипотезы</Label>
            <Switch
              id="report-hypotheses"
              checked={reportConfig.include_hypotheses}
              onCheckedChange={(checked) => toggleReportConfig("include_hypotheses", checked)}
            />
          </div>
          {supportsNormalizedView && (
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <Label htmlFor="normalized-view">Normalized view</Label>
              <Switch
                id="normalized-view"
                checked={useNormalizedView}
                onCheckedChange={setUseNormalizedView}
              />
            </div>
          )}
        </CardContent>
      </Card>

      <StatisticalSummary result={result} />
      <AnalysisReport report={result.analysis_report} config={reportConfig} comparisonType={result.comparison_type} />
      <ComparisonTable result={result} useNormalized={supportsNormalizedView && useNormalizedView} />
      <ComparisonCharts result={result} useNormalized={supportsNormalizedView && useNormalizedView} />
    </div>
  )
}

function getComparisonTypeLabel(type: ComparisonResult["comparison_type"]): string {
  switch (type) {
    case "cross_database":
      return "Тип сравнения: Сравнение СУБД"
    case "scalability":
      return "Тип сравнения: Анализ масштабируемости"
    case "mixed":
      return "Тип сравнения: Смешанное сравнение"
    case "temporal":
      return "Тип сравнения: Временное сравнение"
    default:
      return "Тип сравнения: Смешанное сравнение"
  }
}
