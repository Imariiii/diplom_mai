"use client"

import { useEffect, useState, startTransition } from "react"
import { ChevronLeft, Code, Database, Download, Loader2, Scale, Server, Settings } from "lucide-react"

import { analyzeComparison, type AnalysisReportConfig, type ComparisonResult, type ComparisonTestInfo } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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

  const baselineTest = result.tests.find((t) => t.id === result.baseline_id)

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
          <CardDescription>
            {result.tests.map((test) => test.name).join(" · ")}
            {baselineTest && <span className="ml-2 text-xs">(baseline: {baselineTest.name})</span>}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{getComparisonTypeLabel(result.comparison_type)}</Badge>
            {supportsNormalizedView && (
              <Badge variant="outline">Нормализация доступна</Badge>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {result.tests.map((test) => (
              <TestInfoCard
                key={test.id}
                test={test}
                isBaseline={test.id === result.baseline_id}
              />
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

function TestInfoCard({ test, isBaseline }: { test: ComparisonTestInfo; isBaseline: boolean }) {
  const [queriesOpen, setQueriesOpen] = useState(false)
  const config = test.config || {}
  const scenarioName = test.scenario_info?.name || config.scenario || "-"
  const scenarioType = test.scenario_info?.scenario_type
  const queries = test.scenario_info?.queries || []

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return null
    try {
      return new Date(dateStr).toLocaleString("ru-RU", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold truncate">{test.name}</p>
          {test.started_at && (
            <p className="text-xs text-muted-foreground">{formatDate(test.started_at)}</p>
          )}
        </div>
        {isBaseline && <Badge variant="default" className="shrink-0">Baseline</Badge>}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-sm">
          <Settings className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground">Конфигурация:</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 pl-5.5 text-sm">
          <span className="text-muted-foreground">Потоки:</span>
          <span className="font-mono">{config.virtual_users ?? config.threads ?? "-"}</span>
          <span className="text-muted-foreground">Итерации:</span>
          <span className="font-mono">{config.iterations ?? "-"}</span>
          <span className="text-muted-foreground">Прогрев:</span>
          <span className="font-mono">{config.warmup_time != null ? `${config.warmup_time} с` : "-"}</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-sm">
          <Database className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground">Сценарий:</span>
          <span className="font-medium">{scenarioName}</span>
        </div>
        {scenarioType && scenarioType !== scenarioName && (
          <p className="pl-5.5 text-xs text-muted-foreground">Тип: {scenarioType}</p>
        )}
        {test.scenario_info?.description && (
          <p className="pl-5.5 text-xs text-muted-foreground">{test.scenario_info.description}</p>
        )}
      </div>

      {test.connections.length > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-sm">
            <Server className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-muted-foreground">Подключения:</span>
          </div>
          <div className="pl-5.5 space-y-1">
            {test.connections.map((conn) => (
              <div key={conn.id} className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className="text-xs px-1.5 py-0">{conn.dbms_type}</Badge>
                <span className="font-medium">{conn.name}</span>
                <span className="text-xs text-muted-foreground">{conn.host}:{conn.port}/{conn.database}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {queries.length > 0 && (
        <Collapsible open={queriesOpen} onOpenChange={setQueriesOpen}>
          <CollapsibleTrigger asChild>
            <button className="flex items-center gap-2 text-sm text-primary hover:underline">
              <Code className="h-3.5 w-3.5 shrink-0" />
              Запросы сценария ({queries.length})
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {queries.map((q, idx) => (
              <div key={idx} className="rounded border border-border bg-background p-2.5 space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs px-1.5 py-0 uppercase">{q.query_type}</Badge>
                  <span className="text-xs text-muted-foreground">вес: {q.weight}</span>
                  {q.description && <span className="text-xs text-muted-foreground">— {q.description}</span>}
                </div>
                <pre className="text-xs font-mono bg-muted/50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">{q.sql_template}</pre>
              </div>
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}

function getComparisonTypeLabel(type: ComparisonResult["comparison_type"]): string {
  switch (type) {
    case "cross_database":
      return "Сравнение СУБД"
    case "scalability":
      return "Анализ масштабируемости"
    case "mixed":
      return "Смешанное сравнение"
    case "temporal":
      return "Временное сравнение"
    default:
      return "Смешанное сравнение"
  }
}
