"use client"

import { useEffect, useMemo, useState, startTransition } from "react"
import {
  ChevronLeft,
  Download,
  Loader2,
  Scale,
  SlidersHorizontal,
  AlertTriangle,
  BarChart3,
  Table2,
  Sigma,
  FileText,
  TrendingUp,
  Activity,
  Target,
  Award,
} from "lucide-react"

import {
  analyzeComparison,
  type ComparisonResult,
  type AnalysisWarning,
  isPerTestResult,
  isSeriesResult,
} from "@/lib/api"
import { useAppStore } from "@/lib/store"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { ExecutiveSummary } from "@/components/comparison/executive-summary"
import { ParameterImpact } from "@/components/comparison/parameter-impact"
import { ComparisonTable } from "@/components/comparison/comparison-table"
import { ComparisonCharts } from "@/components/comparison/comparison-charts"
import { StatisticalSummary } from "@/components/comparison/statistical-summary"
import { AnalysisReport } from "@/components/comparison/analysis-report"
import { TestConfigSection } from "@/components/comparison/test-config-section"
import { ResourceMetricsPanel } from "@/components/comparison/resource-metrics-panel"

const MODE_LABELS: Record<string, string> = {
  per_test: "Внутритестовый анализ",
  series: "Серийный анализ",
}

export function ComparisonPage() {
  const { comparisonTestIds, comparisonBaselineId, analysisMode, setCurrentPage } = useAppStore()

  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState(
    analysisMode === "per_test" ? "rankings" : "summary"
  )

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (analysisMode === "per_test" && comparisonTestIds.length !== 1) {
        setError("Для внутритестового анализа выберите ровно один прогон")
        setLoading(false)
        return
      }
      if (analysisMode === "series" && comparisonTestIds.length < 2) {
        setError("Для серийного анализа выберите минимум два прогона")
        setLoading(false)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const response = await analyzeComparison({
          analysis_mode: analysisMode,
          test_ids: comparisonTestIds,
          baseline_id: analysisMode === "series" ? (comparisonBaselineId || comparisonTestIds[0]) : undefined,
        })
        if (!cancelled) {
          startTransition(() => setResult(response))
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Ошибка анализа")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [comparisonTestIds, comparisonBaselineId, analysisMode])

  const exportJson = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `analysis-${analysisMode}-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const perTestTabs = useMemo(
    () => [
      { value: "rankings", label: "Ранги", icon: Award },
      { value: "charts", label: "Графики по СУБД", icon: BarChart3 },
      { value: "stats", label: "Статистика пар", icon: Sigma },
      { value: "report", label: "Отчёт", icon: FileText },
    ],
    []
  )

  const seriesTabs = useMemo(
    () => [
      { value: "summary", label: "Траектории", icon: TrendingUp },
      { value: "degradation", label: "Деградация p95–p99", icon: Activity },
      { value: "stability", label: "Устойчивость (CV)", icon: Target },
      { value: "charts", label: "Графики", icon: BarChart3 },
      { value: "rankings", label: "Ранги по нагрузкам", icon: Award },
      { value: "report", label: "Отчёт", icon: FileText },
    ],
    []
  )

  const tabs = analysisMode === "per_test" ? perTestTabs : seriesTabs

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-sm">Анализируем результаты...</p>
        </div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <Button variant="ghost" size="sm" onClick={() => setCurrentPage("history")}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Назад к истории
        </Button>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Не удалось загрузить анализ</AlertTitle>
          <AlertDescription>{error || "Данные анализа отсутствуют"}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const warnings: AnalysisWarning[] = result.warnings ?? []
  const testNames = isPerTestResult(result)
    ? result.test.name
    : result.tests.map((t) => t.name).join(" · ")

  return (
    <div className="bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 h-8 px-2"
              onClick={() => setCurrentPage("history")}
            >
              <ChevronLeft className="h-4 w-4" />
              <span className="sr-only">Назад</span>
            </Button>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Scale className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base font-semibold leading-none tracking-tight md:text-lg">
                  Анализ прогонов
                </h1>
                <Badge variant="secondary" className="text-[10px] uppercase tracking-wider">
                  {MODE_LABELS[analysisMode]}
                </Badge>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {testNames}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm">
                  <SlidersHorizontal className="mr-2 h-3.5 w-3.5" />
                  Конфигурация
                </Button>
              </SheetTrigger>
              <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
                <SheetHeader>
                  <SheetTitle>Конфигурация прогонов</SheetTitle>
                  <SheetDescription>
                    Параметры прогонов, подключения и сценарии
                  </SheetDescription>
                </SheetHeader>
                <div className="mt-4 px-4 pb-6">
                  <TestConfigSection result={result} />
                </div>
              </SheetContent>
            </Sheet>

            <Button size="sm" onClick={exportJson}>
              <Download className="mr-2 h-3.5 w-3.5" />
              Экспорт
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 md:px-6">
        <ExecutiveSummary result={result} />

        <ResourceMetricsPanel result={result} />

        {warnings.length > 0 && <WarningsCard warnings={warnings} />}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="h-auto w-full justify-start overflow-x-auto rounded-lg border border-border bg-card p-1">
            {tabs.map((t) => {
              const Icon = t.icon
              return (
                <TabsTrigger
                  key={t.value}
                  value={t.value}
                  className="gap-2 px-3 py-1.5 text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm"
                >
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {/* Per-test mode tabs */}
          {isPerTestResult(result) && (
            <>
              <TabsContent value="rankings" className="space-y-6 focus-visible:outline-none">
                <ComparisonTable result={result} />
              </TabsContent>
              <TabsContent value="charts" className="space-y-4 focus-visible:outline-none">
                <ComparisonCharts result={result} />
              </TabsContent>
              <TabsContent value="stats" className="focus-visible:outline-none">
                <StatisticalSummary result={result} />
              </TabsContent>
              <TabsContent value="report" className="focus-visible:outline-none">
                <AnalysisReport
                  report={result.analysis_report}
                  analysisMode={analysisMode}
                />
              </TabsContent>
            </>
          )}

          {/* Series mode tabs */}
          {isSeriesResult(result) && (
            <>
              <TabsContent value="summary" className="space-y-6 focus-visible:outline-none">
                <ParameterImpact result={result} />
              </TabsContent>
              <TabsContent value="degradation" className="space-y-6 focus-visible:outline-none">
                <ComparisonCharts result={result} chartFocus="degradation" />
              </TabsContent>
              <TabsContent value="stability" className="space-y-6 focus-visible:outline-none">
                <ComparisonCharts result={result} chartFocus="stability" />
              </TabsContent>
              <TabsContent value="charts" className="space-y-4 focus-visible:outline-none">
                <ComparisonCharts result={result} />
              </TabsContent>
              <TabsContent value="rankings" className="focus-visible:outline-none">
                <ComparisonTable result={result} />
              </TabsContent>
              <TabsContent value="report" className="focus-visible:outline-none">
                <AnalysisReport
                  report={result.analysis_report}
                  analysisMode={analysisMode}
                />
              </TabsContent>
            </>
          )}
        </Tabs>
      </div>
    </div>
  )
}

function WarningsCard({ warnings }: { warnings: AnalysisWarning[] }) {
  return (
    <div className="rounded-xl border border-warning/30 bg-warning/5 p-4">
      <div className="mb-2 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-warning/15 text-warning">
          <AlertTriangle className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-sm font-medium">Предупреждения анализа</p>
          <p className="text-xs text-muted-foreground">
            Обратите внимание — возможно влияние на достоверность
          </p>
        </div>
      </div>
      <ul className="mt-3 grid gap-1.5 pl-9 text-sm text-muted-foreground md:grid-cols-2">
        {warnings.map((w, i) => (
          <li key={i} className="leading-relaxed">
            <Badge variant="outline" className="mr-1 text-[10px] px-1 py-0">
              {w.severity}
            </Badge>
            {w.message}
          </li>
        ))}
      </ul>
    </div>
  )
}
