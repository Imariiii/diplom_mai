"use client"

import { useState, useEffect } from "react"
import { History, RefreshCw, Trash2, Eye, ChevronLeft, ChevronRight, Clock, CheckCircle, XCircle, Loader2, AlertCircle, GitCompare } from "lucide-react"
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
  LineChart,
  Line,
} from "recharts"

const STATUS_CONFIG = {
  pending: { label: "Ожидание", icon: Clock, color: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" },
  running: { label: "Выполняется", icon: Loader2, color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  completed: { label: "Завершён", icon: CheckCircle, color: "bg-green-500/10 text-green-500 border-green-500/20" },
  failed: { label: "Ошибка", icon: XCircle, color: "bg-red-500/10 text-red-500 border-red-500/20" },
}

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
  const pageSize = 20

  const fetchTests = async () => {
    setLoading(true)
    setError(null)
    try {
      const enabledCheck = await apiClient.isHistoryEnabled()
      if (!enabledCheck.enabled) {
        setHistoryEnabled(false)
        setLoading(false)
        return
      }

      const response = await apiClient.getHistoryTests({ limit: pageSize, offset: page * pageSize })
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

  useEffect(() => {
    fetchTests()
  }, [page])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleString("ru-RU")
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return mins > 0 ? `${mins}м ${secs}с` : `${secs}с`
  }

  const totalPages = Math.ceil(total / pageSize)
  const comparableTests = tests.filter((test) => test.status === "completed")
  const selectionWarning = selectedIds.length > 5
    ? "Можно выбрать не более 5 тестов"
    : selectedIds.length > 0 && selectedIds.length < 2
      ? "Для сравнения выберите минимум 2 завершённых теста"
      : null

  const toggleSelection = (testId: string, checked: boolean) => {
    setSelectedIds((current) => {
      if (checked) {
        if (current.length >= 5) {
          return current
        }
        return current.includes(testId) ? current : [...current, testId]
      }
      return current.filter((id) => id !== testId)
    })
  }

  const goToComparison = () => {
    if (selectedIds.length < 2 || selectedIds.length > 5) {
      return
    }

    setComparisonSelection(selectedIds, selectedIds[0])
    setCurrentPage("comparison")
  }

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
            <Button onClick={fetchTests}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Повторить
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (selectedTest) {
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
                <CardDescription>
                  ID: {selectedTest.id}
                </CardDescription>
              </div>
              <Badge className={STATUS_CONFIG[selectedTest.status].color}>
                {STATUS_CONFIG[selectedTest.status].label}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
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

        <Tabs defaultValue="results" className="space-y-4">
          <TabsList>
            <TabsTrigger value="results">Результаты</TabsTrigger>
            <TabsTrigger value="charts">Графики</TabsTrigger>
            <TabsTrigger value="config">Конфигурация</TabsTrigger>
          </TabsList>

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
                        <TableCell className="text-right font-mono">
                          {result.metrics?.avg_time_ms?.toFixed(2) ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.p50_time_ms?.toFixed(2) ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.p95_time_ms?.toFixed(2) ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.p99_time_ms?.toFixed(2) ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.tps?.toFixed(2) ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.successful ?? "-"}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {result.metrics?.failed ?? "-"}
                        </TableCell>
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
                          p99: r.metrics?.p99_time_ms ?? 0,
                          color: getDbColor((r.metrics as any)?.dbms_type || r.db_type),
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
                          {selectedTest.results.map((r, i) => (
                            <Cell key={i} fill={METRIC_COLORS.avg} />
                          ))}
                        </Bar>
                        <Bar dataKey="p95" name="P95" fill={METRIC_COLORS.p95}>
                          {selectedTest.results.map((r, i) => (
                            <Cell key={i} fill={METRIC_COLORS.p95} />
                          ))}
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
                          color: getDbColor((r.metrics as any)?.dbms_type || r.db_type),
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
                          {selectedTest.results.map((r, i) => (
                            <Cell key={i} fill={CHART_COLORS.success} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="config">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Конфигурация теста</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
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

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">История тестов</h1>
          <p className="text-muted-foreground">Просмотр результатов всех запущенных тестов</p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={goToComparison}
            disabled={selectedIds.length < 2 || selectedIds.length > 5}
          >
            <GitCompare className="h-4 w-4 mr-2" />
            Сравнить выбранные
          </Button>
          <Button onClick={fetchTests} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      <Card className="bg-card border-border">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-medium">Выбрано для сравнения: {selectedIds.length}</p>
            <p className="text-sm text-muted-foreground">
              Доступно завершённых тестов: {comparableTests.length}. Можно выбрать от 2 до 5.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setSelectedIds([])}
              disabled={selectedIds.length === 0}
            >
              Сбросить выбор
            </Button>
          </div>
        </CardContent>
      </Card>

      {selectionWarning && (
        <Alert className="border-amber-500/30 bg-amber-500/5">
          <AlertCircle className="h-4 w-4 text-amber-500" />
          <AlertTitle>Выбор тестов</AlertTitle>
          <AlertDescription>{selectionWarning}</AlertDescription>
        </Alert>
      )}

      <Card className="bg-card border-border">
        <CardContent className="p-0">
          {tests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">История тестов пуста</p>
              <p className="text-sm text-muted-foreground">Запустите первый тест на странице "Конфигурация и запуск"</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">Выбор</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Статус</TableHead>
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
                  const selectionDisabled = !isCompleted || (!isChecked && selectedIds.length >= 5)
                  return (
                    <TableRow key={test.id}>
                      <TableCell>
                        <Checkbox
                          checked={isChecked}
                          disabled={selectionDisabled}
                          onCheckedChange={(checked) => toggleSelection(test.id, checked === true)}
                          aria-label={`Выбрать тест ${test.name}`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{test.name}</TableCell>
                      <TableCell>
                        <Badge className={STATUS_CONFIG[test.status].color}>
                          <StatusIcon className={`h-3 w-3 mr-1 ${test.status === "running" ? "animate-spin" : ""}`} />
                          {STATUS_CONFIG[test.status].label}
                        </Badge>
                      </TableCell>
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
