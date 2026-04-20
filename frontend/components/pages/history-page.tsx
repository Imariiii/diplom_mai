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
  Activity,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { apiClient, type HistoryTestRun, type HistoryTestResult } from "@/lib/api"
import { useAppStore } from "@/lib/store"
import { DB_NAMES, getDbColor, CHART_COLORS, METRIC_COLORS } from "@/lib/chart-colors"
import type { LogicalDatabaseWithConnections } from "@/lib/types"
import { HistoryTimeSeriesTab } from "./history-time-series-tab"
import { cn } from "@/lib/utils"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts"

const STATUS_CONFIG = {
  pending:   { label: "Ожидание",    icon: Clock,         color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" },
  running:   { label: "Выполняется", icon: Loader2,       color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  completed: { label: "Завершён",    icon: CheckCircle,   color: "bg-green-500/10 text-green-500 border-green-500/20" },
  failed:    { label: "Ошибка",      icon: XCircle,       color: "bg-red-500/10 text-red-500 border-red-500/20" },
}

function getResultSelfCheckWarnings(result: HistoryTestResult): string[] {
  const warnings = result.metrics?.self_check?.warnings
  if (!Array.isArray(warnings)) {
    return []
  }
  return warnings.filter((warning): warning is string => typeof warning === "string" && warning.length > 0)
}

// ==================== Селектор логической БД ====================

function LogicalDbFilter({
  databases,
  selectedId,
  onSelect,
}: {
  databases: LogicalDatabaseWithConnections[]
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="h-4 w-4 text-primary" />
          Фильтр по базе данных
        </CardTitle>
        <CardDescription>Выберите логическую базу данных или просматривайте все тесты</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onSelect(null)}
            className={cn(
              "px-3 py-1.5 rounded-md border text-sm transition-colors",
              selectedId === null
                ? "border-primary bg-primary/10 font-medium"
                : "border-border hover:border-muted-foreground"
            )}
          >
            Все базы данных
          </button>
          {databases.map((db) => (
            <button
              key={db.id}
              onClick={() => onSelect(db.id)}
              className={cn(
                "px-3 py-1.5 rounded-md border text-sm transition-colors",
                selectedId === db.id
                  ? "border-primary bg-primary/10 font-medium"
                  : "border-border hover:border-muted-foreground"
              )}
            >
              {db.name}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ==================== Основной компонент ====================

export function HistoryPage() {
  const { setCurrentPage, setComparisonSelection } = useAppStore()

  const [tests, setTests] = useState<HistoryTestRun[]>([])
  const [selectedTest, setSelectedTest] = useState<(HistoryTestRun & { results: HistoryTestResult[] }) | null>(null)
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
      const details = await apiClient.getHistoryTest(testId)
      setSelectedTest(details)
    } catch (err) {
      console.error("Error fetching test details:", err)
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
    setActiveDetailTab("results")
  }, [selectedTest?.id])

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
          <Button variant="ghost" onClick={() => setSelectedTest(null)}>
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

        <Tabs value={activeDetailTab} onValueChange={setActiveDetailTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="results">Результаты</TabsTrigger>
            <TabsTrigger value="charts">Графики</TabsTrigger>
            <TabsTrigger value="monitoring" className="gap-1.5">
              <Activity className="h-3.5 w-3.5" />
              Мониторинг
            </TabsTrigger>
            <TabsTrigger value="config">Конфигурация</TabsTrigger>
          </TabsList>

          <TabsContent value="results">
            {resultsWithWarnings.length > 0 && (
              <Alert className="mb-4 border-amber-500/30 bg-amber-500/5">
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

          <TabsContent value="charts">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="bg-card border-border">
                <CardHeader>
                  <CardTitle>Время отклика</CardTitle>
                  <CardDescription>Среднее время по СУБД</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={selectedTest.results.map(r => ({
                          name: (r.metrics as any)?.db_name || DB_NAMES[(r.metrics as any)?.dbms_type || r.db_type] || r.db_type,
                          avg: r.metrics?.avg_time_ms ?? 0,
                          p95: r.metrics?.p95_time_ms ?? 0,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis dataKey="name" stroke={CHART_COLORS.axis} fontSize={12} tick={{ fill: CHART_COLORS.text }} />
                        <YAxis stroke={CHART_COLORS.axis} fontSize={12} tick={{ fill: CHART_COLORS.text }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
                          itemStyle={{ color: "hsl(var(--foreground))" }}
                          labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                        />
                        <Legend wrapperStyle={{ color: CHART_COLORS.text, paddingTop: "10px" }} />
                        <Bar dataKey="avg" name="Среднее" fill={METRIC_COLORS.avg}>
                          {selectedTest.results.map((_, i) => <Cell key={i} fill={METRIC_COLORS.avg} />)}
                        </Bar>
                        <Bar dataKey="p95" name="P95" fill={METRIC_COLORS.p95}>
                          {selectedTest.results.map((_, i) => <Cell key={i} fill={METRIC_COLORS.p95} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card border-border">
                <CardHeader>
                  <CardTitle>Производительность (TPS)</CardTitle>
                  <CardDescription>Транзакций в секунду</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={selectedTest.results.map(r => ({
                          name: (r.metrics as any)?.db_name || DB_NAMES[(r.metrics as any)?.dbms_type || r.db_type] || r.db_type,
                          tps: r.metrics?.tps ?? 0,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis dataKey="name" stroke={CHART_COLORS.axis} fontSize={12} tick={{ fill: CHART_COLORS.text }} />
                        <YAxis stroke={CHART_COLORS.axis} fontSize={12} tick={{ fill: CHART_COLORS.text }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
                          itemStyle={{ color: "hsl(var(--foreground))" }}
                          labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                        />
                        <Bar dataKey="tps" name="TPS" fill={CHART_COLORS.success}>
                          {selectedTest.results.map((_, i) => <Cell key={i} fill={CHART_COLORS.success} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="monitoring">
            {activeDetailTab === "monitoring" && (
              <HistoryTimeSeriesTab testId={selectedTest.id} />
            )}
          </TabsContent>

          <TabsContent value="config">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Конфигурация теста</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
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
                    <p className="font-mono">{selectedTest.config?.db_types?.join(", ") || "-"}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Сценарий</p>
                    <p className="font-mono">{selectedTest.config?.scenario || "-"}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Итерации</p>
                    <p className="font-mono">{selectedTest.config?.iterations || "-"}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Виртуальные пользователи</p>
                    <p className="font-mono">{selectedTest.config?.virtual_users || "-"}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Прогрев (сек)</p>
                    <p className="font-mono">{selectedTest.config?.warmup_time || "-"}</p>
                  </div>
                </div>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">История тестов</h1>
          <p className="text-muted-foreground">Просмотр результатов всех запущенных тестов</p>
        </div>
        <div className="flex gap-2">
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

      {/* Фильтр по логической БД */}
      <LogicalDbFilter
        databases={logicalDatabases}
        selectedId={selectedLogicalDbId}
        onSelect={handleLogicalDbChange}
      />

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
                {tests.map((test) => {
                  const StatusIcon = STATUS_CONFIG[test.status].icon
                  const isCompleted = test.status === "completed"
                  const isChecked = selectedIds.includes(test.id)
                  const scenarioMismatch = !isChecked && !isScenarioCompatible(test)
                  const selectionDisabled = !isCompleted || (!isChecked && selectedIds.length >= 5) || scenarioMismatch
                  return (
                    <TableRow key={test.id}>
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
