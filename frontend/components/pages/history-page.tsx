"use client"

import { useState, useEffect } from "react"
import {
  History,
  RefreshCw,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  AlertTriangle,
  GitCompare,
  Database,
  LayoutDashboard,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { apiClient, type HistoryTestRun, type HistoryTestResult, type HistoryErrorReport } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { getVisibleSelfCheckWarnings } from "@/lib/self-check"
import type { LogicalDatabaseWithConnections } from "@/lib/types"
import { HistoryTestDashboard } from "./history-test-dashboard"

const STATUS_CONFIG = {
  pending:   { label: "Ожидание",    icon: Clock,         color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" },
  running:   { label: "Выполняется", icon: Loader2,       color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  completed: { label: "Завершён",    icon: CheckCircle,   color: "bg-green-500/10 text-green-500 border-green-500/20" },
  failed:    { label: "Ошибка",      icon: XCircle,       color: "bg-red-500/10 text-red-500 border-red-500/20" },
}

function getResultSelfCheckWarnings(result: HistoryTestResult): string[] {
  return getVisibleSelfCheckWarnings(result.metrics?.self_check)
}

/** Подпись для полей профиля/bundle в режиме пользовательского SQL */
const CONFIG_CUSTOM_SQL_NA = "Не задаётся (пользовательский SQL)"

function formatConfigNumber(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "—"
  return String(value)
}

function formatConfigBooleanRu(value: boolean | undefined | null): string {
  if (value === undefined || value === null) return "—"
  return value ? "Да" : "Нет"
}

function inferDbTypesFromResults(results: HistoryTestResult[] | undefined): string | null {
  if (!results?.length) return null
  const labels = new Set<string>()
  for (const r of results) {
    const m = r.metrics as Record<string, unknown> | undefined
    const raw = (m?.dbms_type as string) || r.db_type
    if (raw) labels.add(DB_NAMES[raw] || raw)
  }
  if (labels.size === 0) return null
  return [...labels].join(", ")
}

function getHistoryDbTypesLabel(
  test: HistoryTestRun & { results?: HistoryTestResult[] },
  logicalDatabases: LogicalDatabaseWithConnections[],
): string {
  const cfg = test.config
  if (!cfg) return "—"
  if (cfg.db_types?.length) {
    return cfg.db_types.map((t) => DB_NAMES[t] || t).join(", ")
  }
  const connIds = cfg.connection_ids
  if (!connIds?.length) {
    return inferDbTypesFromResults(test.results) || "—"
  }
  const ldId = test.logical_database_id || cfg.logical_database_id
  const ld = ldId ? logicalDatabases.find((d) => d.id === ldId) : null
  if (ld) {
    const perConn = connIds
      .map((id) => {
        const c = ld.connections.find((item) => item.id === id)
        return c?.dbms_type ? (DB_NAMES[c.dbms_type] || c.dbms_type) : null
      })
      .filter((v): v is string => Boolean(v))
    if (perConn.length) return [...new Set(perConn)].join(", ")
  }
  return inferDbTypesFromResults(test.results) || "—"
}

function getHistoryProfileLabel(test: HistoryTestRun): string {
  const cfg = test.config
  if (!cfg) return "—"
  if (cfg.scenario === "custom") return CONFIG_CUSTOM_SQL_NA
  const snap = cfg.resolved_bundle_snapshot
  return (
    cfg.resolved_profile_name
    || cfg.resolved_profile_id
    || snap?.schema_profile_name
    || snap?.schema_profile_id
    || "—"
  )
}

function getHistoryBundleLabel(test: HistoryTestRun): string {
  const cfg = test.config
  if (!cfg) return "—"
  if (cfg.scenario === "custom") return CONFIG_CUSTOM_SQL_NA
  const snap = cfg.resolved_bundle_snapshot
  return (
    cfg.resolved_bundle_name
    || cfg.resolved_bundle_id
    || cfg.bundle_id
    || snap?.name
    || snap?.id
    || "—"
  )
}

function getHistoryScenarioTemplateLabel(test: HistoryTestRun): string {
  const cfg = test.config
  if (!cfg) return "—"
  if (cfg.scenario === "custom") return "—"
  const snap = cfg.resolved_bundle_snapshot
  return (
    snap?.scenario_template_name
    || snap?.scenario_template_id
    || cfg.scenario
    || "—"
  )
}

// ==================== Основной компонент ====================

export function HistoryPage() {
  const { setCurrentPage, setComparisonSelection } = useAppStore()

  const [tests, setTests] = useState<HistoryTestRun[]>([])
  const [selectedTest, setSelectedTest] = useState<(HistoryTestRun & { results: HistoryTestResult[] }) | null>(null)
  const [selectedTestErrors, setSelectedTestErrors] = useState<HistoryErrorReport | null>(null)
  const [errorsLoading, setErrorsLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [historyEnabled, setHistoryEnabled] = useState(true)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const [logicalDatabases, setLogicalDatabases] = useState<LogicalDatabaseWithConnections[]>([])
  const [selectedLogicalDbId, setSelectedLogicalDbId] = useState<string | null>(null)
  const [activeDetailTab, setActiveDetailTab] = useState("results")

  const pageSize = 20

  // Загрузка списка логических БД при монтировании
  useEffect(() => {
    apiClient.getLogicalDatabases()
      .then((resp) => setLogicalDatabases(resp.databases))
      .catch(() => {})
  }, [])

  const fetchTests = async (logicalDbId: string | null = selectedLogicalDbId) => {
    setLoading(true)
    setError(null)
    try {
      const enabledCheck = await apiClient.isHistoryEnabled()
      if (!enabledCheck.enabled) {
        setHistoryEnabled(false)
        setLoading(false)
        return
      }

      const params: Parameters<typeof apiClient.getHistoryTests>[0] = {
        limit: pageSize,
        offset: page * pageSize,
      }
      if (logicalDbId) {
        params.logical_database_id = logicalDbId
      }

      const response = await apiClient.getHistoryTests(params)
      setTests(response.tests)
      setTotal(response.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки истории")
    } finally {
      setLoading(false)
    }
  }

  const fetchTestDetails = async (testId: string) => {
    try {
      setSelectedTestErrors(null)
      const details = await apiClient.getHistoryTest(testId)
      setSelectedTest(details)
      setErrorsLoading(true)
      try {
        const errorReport = await apiClient.getHistoryTestErrors(testId)
        setSelectedTestErrors(errorReport)
      } finally {
        setErrorsLoading(false)
      }
    } catch (err) {
      console.error("Error fetching test details:", err)
      setErrorsLoading(false)
    }
  }

  const deleteTest = async (testId: string) => {
    if (!confirm("Удалить этот тест из истории?")) return
    try {
      await apiClient.deleteHistoryTest(testId)
      setTests(tests.filter(t => t.id !== testId))
      setSelectedIds((current) => current.filter((id) => id !== testId))
      if (selectedTest?.id === testId) {
        setSelectedTest(null)
        setSelectedTestErrors(null)
      }
    } catch (err) {
      console.error("Error deleting test:", err)
    }
  }

  // Сбрасываем страницу при смене фильтра
  const handleLogicalDbChange = (id: string | null) => {
    setSelectedLogicalDbId(id)
    setPage(0)
    setSelectedIds([])
    void fetchTests(id)
  }

  useEffect(() => {
    void fetchTests()
  }, [page])

  useEffect(() => {
    setActiveDetailTab(selectedTest?.status === "completed" ? "dashboard" : "results")
  }, [selectedTest?.id, selectedTest?.status])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleString("ru-RU")
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return mins > 0 ? `${mins}м ${secs}с` : `${secs}с`
  }

  const getLogicalDbName = (id: string | null): string => {
    if (!id) return "-"
    return logicalDatabases.find((db) => db.id === id)?.name ?? id.slice(0, 8) + "…"
  }

  const getConnectionNamesLabel = (test: HistoryTestRun): string => {
    const targetLogicalDbId = test.logical_database_id || selectedLogicalDbId
    if (!targetLogicalDbId || !test.config?.connection_ids?.length) {
      return "-"
    }

    const logicalDb = logicalDatabases.find((db) => db.id === targetLogicalDbId)
    if (!logicalDb) {
      return test.config.connection_ids.join(", ")
    }

    return test.config.connection_ids
      .map((connectionId) => {
        const connection = logicalDb.connections.find((item) => item.id === connectionId)
        return connection?.name || connectionId
      })
      .join(", ")
  }

  const totalPages = Math.ceil(total / pageSize)
  const comparableTests = tests.filter((test) => test.status === "completed")

  const getTestScenario = (test: HistoryTestRun): string | null => {
    return test.config?.scenario || null
  }

  const firstSelectedTest = selectedIds.length > 0
    ? tests.find((t) => t.id === selectedIds[0])
    : null
  const lockedScenario = firstSelectedTest ? getTestScenario(firstSelectedTest) : null

  const isScenarioCompatible = (test: HistoryTestRun): boolean => {
    if (!lockedScenario) return true
    const testScenario = getTestScenario(test)
    if (!testScenario) return true
    return testScenario === lockedScenario
  }

  const selectionWarning = selectedIds.length > 5
    ? "Можно выбрать не более 5 тестов"
    : null

  const toggleSelection = (testId: string, checked: boolean) => {
    setSelectedIds((current) => {
      if (checked) {
        if (current.length >= 5) return current
        return current.includes(testId) ? current : [...current, testId]
      }
      return current.filter((id) => id !== testId)
    })
  }

  const goToPerTest = () => {
    if (selectedIds.length !== 1) return
    setComparisonSelection(selectedIds, selectedIds[0], "per_test")
    setCurrentPage("comparison")
  }

  const goToSeries = () => {
    if (selectedIds.length < 2 || selectedIds.length > 5) return
    setComparisonSelection(selectedIds, selectedIds[0], "series")
    setCurrentPage("comparison")
  }

  // ==================== Состояния загрузки / ошибок ====================

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!historyEnabled) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Card className="bg-card border-border max-w-md">
          <CardHeader className="text-center">
            <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <CardTitle>История отключена</CardTitle>
            <CardDescription>
              База данных истории не настроена. Запустите инициализацию БД:
              <code className="block mt-2 p-2 bg-muted rounded text-sm">
                python backend/scripts/init_history_db.py --docker
              </code>
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Card className="bg-card border-border max-w-md">
          <CardHeader className="text-center">
            <AlertCircle className="h-12 w-12 mx-auto text-destructive mb-4" />
            <CardTitle>Ошибка</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <Button onClick={() => fetchTests()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Повторить
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ==================== Детали теста ====================

  if (selectedTest) {
    const logicalDbName = getLogicalDbName(selectedTest.logical_database_id)
    const selectedLogicalDbEntry = logicalDatabases.find((d) => d.id === selectedTest.logical_database_id)
    const connectionNames = getConnectionNamesLabel(selectedTest)
    const resultsWithWarnings = selectedTest.results
      .map((result) => ({
        result,
        warnings: getResultSelfCheckWarnings(result),
      }))
      .filter((item) => item.warnings.length > 0)
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => {
              setSelectedTest(null)
              setSelectedTestErrors(null)
            }}
          >
            <ChevronLeft className="h-4 w-4 mr-2" />
            Назад к списку
          </Button>
        </div>

        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>{selectedTest.name}</CardTitle>
                <CardDescription>ID: {selectedTest.id}</CardDescription>
              </div>
              <Badge className={STATUS_CONFIG[selectedTest.status].color}>
                {STATUS_CONFIG[selectedTest.status].label}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">База данных</p>
                <p className="font-medium">{logicalDbName}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Начало</p>
                <p className="font-mono">{formatDate(selectedTest.started_at)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Окончание</p>
                <p className="font-mono">{formatDate(selectedTest.finished_at)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Транзакций</p>
                <p className="font-mono">{selectedTest.summary?.total_transactions ?? "-"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">TPS</p>
                <p className="font-mono">{selectedTest.summary?.overall_tps?.toFixed(2) ?? "-"}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {resultsWithWarnings.length > 0 && (
          <Alert className="border-amber-500/30 bg-amber-500/5">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <AlertTitle>Предупреждения самопроверки</AlertTitle>
            <AlertDescription className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Для части результатов система нашла возможные расхождения в согласованности метрик.
              </p>
              <div className="space-y-3">
                {resultsWithWarnings.map(({ result, warnings }) => {
                  const resultDbType = (result.metrics as any)?.dbms_type || result.db_type
                  const resultDbName =
                    (result.metrics as any)?.db_name
                    || DB_NAMES[resultDbType]
                    || result.db_type
                  return (
                    <div
                      key={`warning-${result.id}`}
                      className="rounded-md border border-amber-500/20 bg-background/60 p-3"
                    >
                      <p className="text-sm font-medium">
                        {resultDbName}
                        {result.query_id ? ` · ${result.query_id}` : ""}
                      </p>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                        {warnings.map((warning) => (
                          <li key={`${result.id}-${warning}`}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>
            </AlertDescription>
          </Alert>
        )}

        <Tabs value={activeDetailTab} onValueChange={setActiveDetailTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="dashboard" className="gap-1.5">
              <LayoutDashboard className="h-3.5 w-3.5" />
              Дашборд
            </TabsTrigger>
            <TabsTrigger value="results">Результаты</TabsTrigger>
            <TabsTrigger value="errors" className="gap-1.5">
              Ошибки
              {(selectedTestErrors?.total_errors ?? 0) > 0 && (
                <Badge variant="destructive" className="h-5 px-1.5 text-[10px]">
                  {selectedTestErrors?.total_errors}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="config">Конфигурация</TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-4 focus-visible:outline-none">
            <HistoryTestDashboard
              key={selectedTest.id}
              test={selectedTest}
              virtualUsers={selectedTest.config?.virtual_users ?? 0}
            />
          </TabsContent>

          <TabsContent value="results">
            <Card className="bg-card border-border">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>СУБД</TableHead>
                      <TableHead>Запрос</TableHead>
                      <TableHead className="text-right">Ср. время (мс)</TableHead>
                      <TableHead className="text-right">P50 (мс)</TableHead>
                      <TableHead className="text-right">P95 (мс)</TableHead>
                      <TableHead className="text-right">P99 (мс)</TableHead>
                      <TableHead className="text-right">TPS</TableHead>
                      <TableHead className="text-right">Успешных</TableHead>
                      <TableHead className="text-right">Ошибок</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedTest.results.map((result) => (
                      <TableRow key={result.id}>
                        <TableCell>
                          <span style={{ color: getDbColor((result.metrics as any)?.dbms_type || result.db_type) }} className="font-medium">
                            {(result.metrics as any)?.db_name || DB_NAMES[(result.metrics as any)?.dbms_type || result.db_type] || result.db_type}
                          </span>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{result.query_id || "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.avg_time_ms?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.p50_time_ms?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.p95_time_ms?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.p99_time_ms?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.tps?.toFixed(2) ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.successful ?? "-"}</TableCell>
                        <TableCell className="text-right font-mono">{result.metrics?.failed ?? "-"}</TableCell>
                      </TableRow>
                    ))}
                    {selectedTest.results.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={9} className="text-center text-muted-foreground">
                          Нет результатов
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="errors" className="space-y-4">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Ошибки запросов</CardTitle>
                <CardDescription>
                  Сгруппированные ошибки, сохранённые в raw-метриках теста.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {errorsLoading && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Загрузка ошибок...
                  </div>
                )}
                {!errorsLoading && (selectedTestErrors?.total_errors ?? 0) === 0 && (
                  <p className="text-sm text-muted-foreground">Ошибок запросов не найдено.</p>
                )}
                {!errorsLoading && selectedTestErrors && selectedTestErrors.total_errors > 0 && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-muted-foreground">Всего ошибок</p>
                        <p className="font-mono text-xl text-destructive">{selectedTestErrors.total_errors}</p>
                      </div>
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-muted-foreground">Групп ошибок</p>
                        <p className="font-mono text-xl">{selectedTestErrors.groups.length}</p>
                      </div>
                      <div className="rounded-lg border border-border bg-muted/20 p-3">
                        <p className="text-muted-foreground">Примеров показано</p>
                        <p className="font-mono text-xl">{selectedTestErrors.samples.length}</p>
                      </div>
                    </div>

                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Ошибка</TableHead>
                          <TableHead>Запрос</TableHead>
                          <TableHead className="text-right">Количество</TableHead>
                          <TableHead>Первое появление</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedTestErrors.groups.map((group) => (
                          <TableRow key={`${group.message}-${group.query_id}`}>
                            <TableCell className="max-w-[520px]">
                              <p className="font-mono text-xs whitespace-pre-wrap break-words">{group.message}</p>
                              {group.example && group.example !== group.message && (
                                <details className="mt-2 text-xs text-muted-foreground">
                                  <summary className="cursor-pointer">Показать пример</summary>
                                  <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 whitespace-pre-wrap">
                                    {group.example}
                                  </pre>
                                </details>
                              )}
                            </TableCell>
                            <TableCell className="font-mono text-xs">{group.query_id || "-"}</TableCell>
                            <TableCell className="text-right font-mono text-destructive">{group.count}</TableCell>
                            <TableCell className="font-mono text-xs">{formatDate(group.first_seen)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="config">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Конфигурация теста</CardTitle>
                <CardDescription>
                  Параметры запуска из сохранённой записи прогона
                  {selectedTest.config?.test_name ? ` · ${selectedTest.config.test_name}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                  <div>
                    <p className="text-muted-foreground">Логическая БД</p>
                    <p className="font-medium">{logicalDbName}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Подключения</p>
                    <p className="font-mono break-words">{connectionNames}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">СУБД</p>
                    <p className="font-mono break-words">
                      {getHistoryDbTypesLabel(selectedTest, logicalDatabases)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Сценарий (режим)</p>
                    <p className="font-mono">{selectedTest.config?.scenario || "—"}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Шаблон сценария</p>
                    <p className="font-mono break-words">
                      {getHistoryScenarioTemplateLabel(selectedTest)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Профиль схемы</p>
                    <p className="font-mono break-words">{getHistoryProfileLabel(selectedTest)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Bundle</p>
                    <p className="font-mono break-words">{getHistoryBundleLabel(selectedTest)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Итерации</p>
                    <p className="font-mono">{formatConfigNumber(selectedTest.config?.iterations)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Виртуальные пользователи</p>
                    <p className="font-mono">{formatConfigNumber(selectedTest.config?.virtual_users)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Прогрев (сек)</p>
                    <p className="font-mono">{formatConfigNumber(selectedTest.config?.warmup_time)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Индексы сценария</p>
                    <p className="font-mono">{formatConfigBooleanRu(selectedTest.config?.use_indexes)}</p>
                  </div>
                  {selectedTest.config?.query_id && (
                    <div>
                      <p className="text-muted-foreground">Запрос (query_id)</p>
                      <p className="font-mono break-words">{selectedTest.config.query_id}</p>
                    </div>
                  )}
                  {selectedLogicalDbEntry?.schema_profile_name &&
                    selectedTest.config?.scenario === "custom" && (
                    <div className="sm:col-span-2 lg:col-span-3">
                      <p className="text-muted-foreground">Профиль в каталоге (логическая БД)</p>
                      <p className="font-mono break-words text-muted-foreground">
                        {selectedLogicalDbEntry.schema_profile_name}
                        <span className="ml-1 text-xs">
                          (справочно: для custom SQL bundle не используется)
                        </span>
                      </p>
                    </div>
                  )}
                </div>

                {selectedTest.config?.custom_sql && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">Пользовательский SQL</p>
                    <details className="rounded-lg border border-border bg-muted/30">
                      <summary className="cursor-pointer px-3 py-2 text-sm text-muted-foreground">
                        Показать текст запроса ({selectedTest.config.custom_sql.length} симв.)
                      </summary>
                      <pre className="max-h-64 overflow-auto border-t border-border p-3 text-xs font-mono whitespace-pre-wrap break-words">
                        {selectedTest.config.custom_sql}
                      </pre>
                    </details>
                  </div>
                )}

                {selectedTest.config?.connection_ids && selectedTest.config.connection_ids.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">Идентификаторы подключений</p>
                    <ul className="list-inside list-disc space-y-1 font-mono text-xs text-muted-foreground break-all">
                      {selectedTest.config.connection_ids.map((id) => (
                        <li key={id}>{id}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    )
  }

  // ==================== Список тестов ====================

  const showDbColumn = selectedLogicalDbId === null
  const showConnectionsColumn = selectedLogicalDbId !== null

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-bold">История тестов</h1>
          <p className="text-muted-foreground text-pretty">
            Просмотр результатов всех запущенных тестов
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button onClick={goToPerTest} disabled={selectedIds.length !== 1} variant="outline">
            <Eye className="h-4 w-4 mr-2" />
            Сводка по прогону
          </Button>
          <Button onClick={goToSeries} disabled={selectedIds.length < 2 || selectedIds.length > 5}>
            <GitCompare className="h-4 w-4 mr-2" />
            Анализ серии
          </Button>
          <Button onClick={() => fetchTests()} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      {/* Фильтр по логической БД: одиночный выбор через выпадающий список (паттерн «фильтр категории» в панели инструментов) */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-2 sm:max-w-md">
          <Label htmlFor="history-logical-db-filter" className="flex items-center gap-2 text-sm font-medium">
            <Database className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            База данных
          </Label>
          <Select
            value={selectedLogicalDbId ?? "__all__"}
            onValueChange={(value) => {
              handleLogicalDbChange(value === "__all__" ? null : value)
            }}
          >
            <SelectTrigger
              id="history-logical-db-filter"
              size="sm"
              className="h-9 w-full min-w-0 sm:max-w-md"
              aria-label="Фильтр списка тестов по логической базе данных"
            >
              <SelectValue placeholder="Все базы данных" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Все базы данных</SelectItem>
              {logicalDatabases.map((db) => (
                <SelectItem key={db.id} value={db.id}>
                  {db.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {total > 0 && (
          <p className="text-sm text-muted-foreground sm:self-end sm:pb-2">
            Всего записей: <span className="font-mono text-foreground">{total}</span>
            {selectedLogicalDbId ? (
              <>
                {" · "}
                фильтр: <span className="font-medium text-foreground">{getLogicalDbName(selectedLogicalDbId)}</span>
              </>
            ) : null}
          </p>
        )}
      </div>

      {/* Панель выбора для сравнения */}
      <Card className="bg-card border-border">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <p className="font-medium">Выбрано для анализа: {selectedIds.length}</p>
            <p className="text-sm text-muted-foreground">
              Доступно завершённых тестов: {comparableTests.length}. 1 — сводка по прогону, 2–5 — анализ серии.
            </p>
            <div className="flex flex-wrap gap-2">
              {lockedScenario && (
                <Badge variant="secondary" className="text-xs">
                  Сценарий: {lockedScenario}
                </Badge>
              )}
              {selectedLogicalDbId && (
                <Badge variant="secondary" className="text-xs">
                  БД: {getLogicalDbName(selectedLogicalDbId)}
                </Badge>
              )}
            </div>
          </div>
          <Button
            variant="outline"
            onClick={() => setSelectedIds([])}
            disabled={selectedIds.length === 0}
          >
            Сбросить выбор
          </Button>
        </CardContent>
      </Card>

      {selectionWarning && (
        <Alert className="border-amber-500/30 bg-amber-500/5">
          <AlertCircle className="h-4 w-4 text-amber-500" />
          <AlertTitle>Выбор тестов</AlertTitle>
          <AlertDescription>{selectionWarning}</AlertDescription>
        </Alert>
      )}

      {/* Таблица тестов */}
      <Card className="bg-card border-border">
        <CardContent className="p-0">
          {tests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                {selectedLogicalDbId
                  ? `Для базы данных «${getLogicalDbName(selectedLogicalDbId)}» тестов ещё нет`
                  : "История тестов пуста"}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Запустите первый тест на странице «Конфигурация и запуск»
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12 text-right tabular-nums">№</TableHead>
                  <TableHead className="w-12">Выбор</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Статус</TableHead>
                  {showDbColumn && <TableHead>База данных</TableHead>}
                  {showConnectionsColumn && <TableHead>Подключения</TableHead>}
                  <TableHead>Начало</TableHead>
                  <TableHead>Длительность</TableHead>
                  <TableHead className="text-right">Транзакций</TableHead>
                  <TableHead className="text-right">TPS</TableHead>
                  <TableHead className="text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tests.map((test, index) => {
                  const rowNumber = page * pageSize + index + 1
                  const StatusIcon = STATUS_CONFIG[test.status].icon
                  const isCompleted = test.status === "completed"
                  const isChecked = selectedIds.includes(test.id)
                  const scenarioMismatch = !isChecked && !isScenarioCompatible(test)
                  const selectionDisabled = !isCompleted || (!isChecked && selectedIds.length >= 5) || scenarioMismatch
                  return (
                    <TableRow key={test.id}>
                      <TableCell className="text-right font-mono text-sm text-muted-foreground tabular-nums">
                        {rowNumber}
                      </TableCell>
                      <TableCell>
                        <div className="relative group">
                          <Checkbox
                            checked={isChecked}
                            disabled={selectionDisabled}
                            onCheckedChange={(checked) => toggleSelection(test.id, checked === true)}
                            aria-label={`Выбрать тест ${test.name}`}
                          />
                          {scenarioMismatch && (
                            <span className="absolute left-6 top-0 hidden group-hover:block z-10 whitespace-nowrap rounded bg-popover border border-border px-2 py-1 text-xs text-muted-foreground shadow-md">
                              Другой сценарий ({getTestScenario(test) || "?"})
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{test.name}</TableCell>
                      <TableCell>
                        <Badge className={STATUS_CONFIG[test.status].color}>
                          <StatusIcon className={`h-3 w-3 mr-1 ${test.status === "running" ? "animate-spin" : ""}`} />
                          {STATUS_CONFIG[test.status].label}
                        </Badge>
                      </TableCell>
                      {showDbColumn && (
                        <TableCell className="text-sm text-muted-foreground">
                          {test.logical_database_id
                            ? getLogicalDbName(test.logical_database_id)
                            : <span className="text-xs italic">—</span>
                          }
                        </TableCell>
                      )}
                      {showConnectionsColumn && (
                        <TableCell className="max-w-[280px] text-sm text-muted-foreground">
                          <span className="line-clamp-2 break-words">
                            {getConnectionNamesLabel(test)}
                          </span>
                        </TableCell>
                      )}
                      <TableCell className="font-mono text-sm">{formatDate(test.started_at)}</TableCell>
                      <TableCell className="font-mono text-sm">
                        {test.summary?.total_duration ? formatDuration(test.summary.total_duration) : "-"}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {test.summary?.total_transactions ?? "-"}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {test.summary?.overall_tps?.toFixed(2) ?? "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => fetchTestDetails(test.id)}
                            title="Просмотр"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteTest(test.id)}
                            title="Удалить"
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <Button
            variant="outline"
            size="icon"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Страница {page + 1} из {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}
