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
  Settings2,
  Zap,
} from "lucide-react"

import {
  analyzeComparison,
  type AnalysisReportConfig,
  type ComparisonResult,
} from "@/lib/api"
import { useAppStore } from "@/lib/store"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { ExecutiveSummary } from "@/components/comparison/executive-summary"
import { ParameterImpact } from "@/components/comparison/parameter-impact"
import { ComparisonTable } from "@/components/comparison/comparison-table"
import { ComparisonCharts } from "@/components/comparison/comparison-charts"
import { StatisticalSummary } from "@/components/comparison/statistical-summary"
import { AnalysisReport } from "@/components/comparison/analysis-report"
import { TestConfigSection } from "@/components/comparison/test-config-section"

const COMPARISON_TYPE_LABELS: Record<string, string> = {
  cross_database: "Сравнение СУБД",
  scalability: "Анализ масштабируемости",
  config_comparison: "Сравнение конфигураций",
  temporal: "Временное сравнение",
  general: "Общее сравнение",
  mixed: "Сравнение конфигураций",
}

export function ComparisonPage() {
  const { comparisonTestIds, comparisonBaselineId, setCurrentPage } = useAppStore()

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
  const [activeTab, setActiveTab] = useState("params")

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
        })
        if (!cancelled) {
          startTransition(() => setResult(response))
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Ошибка анализа сравнения")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [comparisonTestIds, comparisonBaselineId])

  const supportsNormalizedView = Boolean(
    result && result.traits && !result.traits.same_load_params
  )

  const exportJson = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `comparison-${result.baseline_id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const toggleReport = (key: keyof AnalysisReportConfig, checked: boolean) =>
    setReportConfig((current) => ({ ...current, [key]: checked }))

  const tabs = useMemo(
    () => [
      { value: "params", label: "Параметры", icon: Zap },
      { value: "charts", label: "Графики", icon: BarChart3 },
      { value: "table", label: "Таблица", icon: Table2 },
      { value: "stats", label: "Статистика", icon: Sigma },
      { value: "report", label: "Отчёт", icon: FileText },
    ],
    []
  )

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
          <AlertTitle>Не удалось загрузить сравнение</AlertTitle>
          <AlertDescription>{error || "Данные анализа отсутствуют"}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="bg-background">
      {/* Sticky top bar */}
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
                  Сравнение тестов
                </h1>
                <span className="hidden rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground sm:inline-block">
                  {COMPARISON_TYPE_LABELS[result.comparison_type]}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {result.tests.map((t) => t.name).join(" · ")}
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
                  <SheetTitle>Конфигурация тестов</SheetTitle>
                  <SheetDescription>
                    Параметры прогонов, подключения и сценарии
                  </SheetDescription>
                </SheetHeader>
                <div className="mt-4 px-4 pb-6">
                  <TestConfigSection result={result} />
                </div>
              </SheetContent>
            </Sheet>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm">
                  <Settings2 className="mr-2 h-3.5 w-3.5" />
                  Вид
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-72">
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium">Параметры отображения</h4>
                    <p className="text-xs text-muted-foreground">
                      Управляйте нормализацией и видимыми секциями отчёта
                    </p>
                  </div>
                  <Separator />
                  {supportsNormalizedView && (
                    <div className="flex items-center justify-between gap-2">
                      <Label htmlFor="normalized-view" className="text-sm font-normal">
                        Нормализованный вид
                      </Label>
                      <Switch
                        id="normalized-view"
                        checked={useNormalizedView}
                        onCheckedChange={setUseNormalizedView}
                      />
                    </div>
                  )}
                  <Separator />
                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Секции отчёта
                    </p>
                    {(
                      [
                        ["include_verdict", "Вердикт"],
                        ["include_patterns", "Паттерны"],
                        ["include_recommendations", "Рекомендации"],
                        ["include_hypotheses", "Гипотезы"],
                      ] as const
                    ).map(([key, label]) => (
                      <div key={key} className="flex items-center justify-between gap-2">
                        <Label htmlFor={key} className="text-sm font-normal">
                          {label}
                        </Label>
                        <Switch
                          id={key}
                          checked={reportConfig[key]}
                          onCheckedChange={(c) => toggleReport(key, c)}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            <Button size="sm" onClick={exportJson}>
              <Download className="mr-2 h-3.5 w-3.5" />
              Экспорт
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 md:px-6">
        <ExecutiveSummary result={result} />

        {result.warnings.length > 0 && (
          <WarningsCard warnings={result.warnings} />
        )}

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

          <TabsContent value="params" className="space-y-6 focus-visible:outline-none">
            <ParameterImpact result={result} />
          </TabsContent>

          <TabsContent value="charts" className="space-y-4 focus-visible:outline-none">
            <ComparisonCharts
              result={result}
              useNormalized={supportsNormalizedView && useNormalizedView}
            />
          </TabsContent>

          <TabsContent value="table" className="focus-visible:outline-none">
            <ComparisonTable
              result={result}
              useNormalized={supportsNormalizedView && useNormalizedView}
            />
          </TabsContent>

          <TabsContent value="stats" className="focus-visible:outline-none">
            <StatisticalSummary result={result} />
          </TabsContent>

          <TabsContent value="report" className="focus-visible:outline-none">
            <AnalysisReport
              report={result.analysis_report}
              config={reportConfig}
              comparisonType={result.comparison_type}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function WarningsCard({ warnings }: { warnings: string[] }) {
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
        {warnings.map((w) => (
          <li key={w} className="leading-relaxed">
            — {w}
          </li>
        ))}
      </ul>
    </div>
  )
}
