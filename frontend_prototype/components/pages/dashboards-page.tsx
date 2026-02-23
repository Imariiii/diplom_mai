"use client"

import { useEffect, useState } from "react"
import { Activity, Clock, Cpu, Database, HardDrive, Zap, Users, AlertTriangle, CheckCircle, XCircle, BarChart3, Lock, Gauge, Wifi, WifiOff, Timer, TrendingUp } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { useAppStore } from "@/lib/store"
import { useTestWebSocket } from "@/hooks/use-test-websocket"
import { apiClient } from "@/lib/api"
import { toast } from "sonner"
import { DB_COLORS, DB_NAMES, getDbColor, CHART_COLORS } from "@/lib/chart-colors"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts"

export function DashboardsPage() {
  const { currentTest, realtimeData, testConfig, setCurrentTest, addTestToHistory, clearRealtimeData } = useAppStore()
  const [statusMessage, setStatusMessage] = useState<string>("")

  // WebSocket подключение для real-time обновлений
  const {
    isConnected,
    progress,
    status,
    elapsedSeconds,
    remainingSeconds,
  } = useTestWebSocket({
    testId: currentTest?.id || "",
    onStatus: (data) => {
      setStatusMessage(data.message || "")
      
      // Обновляем статус теста когда он завершается
      if (data.status === "completed" || data.status === "failed") {
        if (currentTest) {
          const updatedTest = {
            ...currentTest,
            status: data.status,
            endTime: new Date(),
          }
          
          // Загружаем финальные результаты
          if (data.status === "completed") {
            apiClient.getAsyncTestResults(currentTest.id).then((response) => {
              if (response.results) {
                const aggregateByDb: Record<string, {
                  avgTimes: number[]
                  p50Times: number[]
                  p95Times: number[]
                  p99Times: number[]
                  minTimes: number[]
                  maxTimes: number[]
                  tpsValues: number[]
                  throughputValues: number[]
                  activeConnections: number[]
                  successful: number
                  failed: number
                }> = {}

                response.results.forEach((result: any) => {
                  const comparison = result.comparison || {}
                  Object.entries(comparison).forEach(([dbType, stats]: [string, any]) => {
                    if (!aggregateByDb[dbType]) {
                      aggregateByDb[dbType] = {
                        avgTimes: [],
                        p50Times: [],
                        p95Times: [],
                        p99Times: [],
                        minTimes: [],
                        maxTimes: [],
                        tpsValues: [],
                        throughputValues: [],
                        activeConnections: [],
                        successful: 0,
                        failed: 0,
                      }
                    }
                    const bucket = aggregateByDb[dbType]
                    if (typeof stats.avg_time_ms === "number") bucket.avgTimes.push(stats.avg_time_ms)
                    if (typeof stats.p50_time_ms === "number") bucket.p50Times.push(stats.p50_time_ms)
                    if (typeof stats.p95_time_ms === "number") bucket.p95Times.push(stats.p95_time_ms)
                    if (typeof stats.p99_time_ms === "number") bucket.p99Times.push(stats.p99_time_ms)
                    if (typeof stats.min_time_ms === "number") bucket.minTimes.push(stats.min_time_ms)
                    if (typeof stats.max_time_ms === "number") bucket.maxTimes.push(stats.max_time_ms)
                    if (typeof stats.tps === "number") bucket.tpsValues.push(stats.tps)
                    if (typeof stats.throughput === "number") bucket.throughputValues.push(stats.throughput)
                    if (typeof stats.active_connections === "number") bucket.activeConnections.push(stats.active_connections)
                    bucket.successful += stats.successful || 0
                    bucket.failed += stats.failed || 0
                  })
                })

                const average = (values: number[]) =>
                  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0

                const formattedResults = Object.entries(aggregateByDb).map(([dbType, bucket]) => {
                  const totalTransactions = bucket.successful + bucket.failed
                  return {
                    databaseId: dbType,
                    databaseName: DB_NAMES[dbType] || dbType,
                    metrics: {
                      avgResponseTime: average(bucket.avgTimes),
                      p50ResponseTime: average(bucket.p50Times),
                      p95ResponseTime: average(bucket.p95Times),
                      p99ResponseTime: average(bucket.p99Times),
                      minResponseTime: bucket.minTimes.length ? Math.min(...bucket.minTimes) : 0,
                      maxResponseTime: bucket.maxTimes.length ? Math.max(...bucket.maxTimes) : 0,
                      tps: average(bucket.tpsValues),
                      throughput: average(bucket.throughputValues),
                      activeConnections: bucket.activeConnections.length
                        ? Math.round(average(bucket.activeConnections))
                        : testConfig.virtualUsers,
                      errorCount: bucket.failed,
                      errorRate: totalTransactions > 0 ? (bucket.failed / totalTransactions) * 100 : 0,
                    },
                    transactionMetrics: {
                      totalTransactions,
                      successfulTransactions: bucket.successful,
                      failedTransactions: bucket.failed,
                      rollbacks: 0,
                    },
                    systemMetrics: response.system_metrics?.[dbType],
                    dbmsMetrics: response.dbms_metrics?.[dbType],
                    timeSeriesData: [],
                  }
                })

                setCurrentTest({
                  ...updatedTest,
                  results: formattedResults,
                })
                addTestToHistory({
                  ...updatedTest,
                  results: formattedResults,
                })
                toast.success("Тестирование завершено!")
              }
            }).catch(console.error)
          } else {
            setCurrentTest(updatedTest)
            toast.error("Тестирование завершилось с ошибкой")
          }
        }
      }
    },
    onConnect: () => {
      toast.success("Подключено к real-time обновлениям")
    },
    onDisconnect: () => {
      if (currentTest?.status === "running") {
        toast.warning("Соединение потеряно, переподключение...")
      }
    },
  })

  // Очищаем данные при размонтировании или смене теста
  useEffect(() => {
    return () => {
      // Не очищаем если тест завершен, чтобы сохранить данные
      if (currentTest?.status !== "completed") {
        clearRealtimeData()
      }
    }
  }, [currentTest?.id])

  // Форматирование времени
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Данные для графиков реального времени
  const chartData = Object.entries(realtimeData).reduce<Record<string, unknown>[]>((acc, [dbId, points]) => {
    points.forEach((point, index) => {
      if (!acc[index]) {
        acc[index] = { time: new Date(point.timestamp).toLocaleTimeString("ru") }
      }
      acc[index][`${dbId}_responseTime`] = point.responseTime?.toFixed(2) || 0
      acc[index][`${dbId}_throughput`] = point.throughput?.toFixed(0) || 0
      acc[index][`${dbId}_tps`] = point.tps?.toFixed(0) || 0
      acc[index][`${dbId}_cpu`] = point.cpuUsage?.toFixed(1) || 0
      acc[index][`${dbId}_memory`] = point.memoryUsage?.toFixed(1) || 0
      acc[index][`${dbId}_diskIO`] = point.diskIOps?.toFixed(0) || 0
      acc[index][`${dbId}_connections`] = point.activeConnections || 0
      acc[index][`${dbId}_errors`] = point.errorCount || 0
    })
    return acc
  }, [])

  const getLatestMetric = (dbId: string, metric: string) => {
    const points = realtimeData[dbId]
    if (!points || points.length === 0) return "—"
    const value = points[points.length - 1][metric as keyof typeof points[number]]
    return typeof value === "number" ? value.toFixed(2) : value
  }

  // Получить результаты для СУБД
  const getResultForDb = (dbId: string) => {
    return currentTest?.results?.find(r => r.databaseId === dbId)
  }

  if (!currentTest && Object.keys(realtimeData).length === 0) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Card className="bg-card border-border max-w-md">
          <CardHeader className="text-center">
            <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <CardTitle className="text-foreground">Нет активных тестов</CardTitle>
            <CardDescription>
              Запустите тестирование на странице &quot;Конфигурация и запуск&quot; для отображения дашбордов
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Дашборды</h1>
          <p className="text-muted-foreground">Мониторинг производительности в реальном времени</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Индикатор WebSocket соединения */}
          <div className="flex items-center gap-1.5">
            {isConnected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-muted-foreground" />
            )}
            <span className="text-xs text-muted-foreground">
              {isConnected ? "Live" : "Offline"}
            </span>
          </div>
          
          {currentTest && (
            <Badge 
              variant={
                currentTest.status === "running" ? "default" : 
                currentTest.status === "completed" ? "secondary" :
                currentTest.status === "failed" ? "destructive" : "outline"
              }
            >
              {currentTest.status === "running" ? "Выполняется" : 
               currentTest.status === "completed" ? "Завершён" :
               currentTest.status === "failed" ? "Ошибка" : "Ожидание"}
            </Badge>
          )}
        </div>
      </div>

      {/* Прогресс бар (только для выполняющихся тестов) */}
      {currentTest?.status === "running" && (
        <Card className="bg-card border-border">
          <CardContent className="pt-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary animate-pulse" />
                  <span className="font-medium">Прогресс тестирования</span>
                </div>
                <span className="font-mono text-primary">{progress.toFixed(1)}%</span>
              </div>
              
              <Progress value={progress} className="h-2" />
              
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <Timer className="h-3 w-3" />
                    Прошло: {formatTime(elapsedSeconds)}
                  </span>
                </div>
                {statusMessage && (
                  <span className="text-primary">{statusMessage}</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Табы для категорий метрик */}
      <Tabs defaultValue="database" className="space-y-4">
        <TabsList className="bg-muted">
          <TabsTrigger value="database" className="text-foreground data-[state=active]:text-foreground">
            <Database className="h-4 w-4 mr-2" />
            База данных
          </TabsTrigger>
          <TabsTrigger value="system" className="text-foreground data-[state=active]:text-foreground">
            <Cpu className="h-4 w-4 mr-2" />
            Системные
          </TabsTrigger>
          <TabsTrigger value="transactions" className="text-foreground data-[state=active]:text-foreground">
            <BarChart3 className="h-4 w-4 mr-2" />
            Транзакции
          </TabsTrigger>
          <TabsTrigger value="dbms" className="text-foreground data-[state=active]:text-foreground">
            <Lock className="h-4 w-4 mr-2" />
            Внутренние СУБД
          </TabsTrigger>
        </TabsList>

        {/* Метрики базы данных */}
        <TabsContent value="database" className="space-y-6">
          {/* Карточки с основными метриками по каждой СУБД */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {testConfig.databases.map((dbId) => {
              const result = getResultForDb(dbId)
              return (
                <Card key={dbId} className="bg-card border-border">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-foreground">
                      <Database className="h-4 w-4" style={{ color: getDbColor(dbId) }} />
                      {DB_NAMES[dbId]}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Avg время</span>
                      <span className="font-mono text-foreground">{result?.metrics?.avgResponseTime?.toFixed(2) || getLatestMetric(dbId, "responseTime")} ms</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">TPS</span>
                      <span className="font-mono text-foreground">{result?.metrics?.tps?.toFixed(0) || getLatestMetric(dbId, "tps")} tx/s</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Соединения</span>
                      <span className="font-mono text-foreground">{result?.metrics?.activeConnections || testConfig.virtualUsers}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Ошибки</span>
                      <span className="font-mono text-foreground">{result?.metrics?.errorCount || 0}</span>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>

          {/* Перцентили времени отклика */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-foreground">
                <Clock className="h-5 w-5 text-primary" />
                Время отклика (перцентили)
              </CardTitle>
              <CardDescription>avg, p50, p95, p99 для каждой СУБД</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {testConfig.databases.map((dbId) => {
                  const result = getResultForDb(dbId)
                  const metrics = result?.metrics
                  return (
                    <div key={dbId} className="p-4 bg-muted rounded-lg">
                      <div className="font-medium mb-3 text-foreground" style={{ color: getDbColor(dbId) }}>
                        {DB_NAMES[dbId]}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Avg:</span>
                          <span className="font-mono text-foreground">{metrics?.avgResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">p50:</span>
                          <span className="font-mono text-foreground">{metrics?.p50ResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">p95:</span>
                          <span className="font-mono text-foreground">{metrics?.p95ResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">p99:</span>
                          <span className="font-mono text-foreground">{metrics?.p99ResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Min:</span>
                          <span className="font-mono text-foreground">{metrics?.minResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Max:</span>
                          <span className="font-mono text-foreground">{metrics?.maxResponseTime?.toFixed(2) || "—"} ms</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* Графики */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Время отклика */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Clock className="h-5 w-5 text-primary" />
                  Время отклика (ms)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Line
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_responseTime`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* TPS */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Gauge className="h-5 w-5 text-primary" />
                  TPS (транзакций/сек)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Area
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_tps`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          fill={getDbColor(dbId)}
                          fillOpacity={0.2}
                        />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Активные соединения */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Users className="h-5 w-5 text-primary" />
                  Активные соединения
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Line
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_connections`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Количество ошибок */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                  Количество ошибок
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Line
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_errors`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          strokeWidth={2}
                          dot={{ fill: getDbColor(dbId), r: 4 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Системные метрики */}
        <TabsContent value="system" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* CPU */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Cpu className="h-5 w-5 text-primary" />
                  Загрузка CPU (%)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        domain={[0, 100]}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Line
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_cpu`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* RAM */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <HardDrive className="h-5 w-5 text-primary" />
                  Использование RAM (%)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        domain={[0, 100]}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Line
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_memory`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Disk I/O */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <HardDrive className="h-5 w-5 text-primary" />
                  Disk I/O (ops/sec)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Area
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_diskIO`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          fill={getDbColor(dbId)}
                          fillOpacity={0.2}
                        />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Пропускная способность */}
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <Zap className="h-5 w-5 text-primary" />
                  Пропускная способность (req/s)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis} 
                        fontSize={12}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                        itemStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      {testConfig.databases.map((dbId) => (
                        <Area
                          key={dbId}
                          type="monotone"
                          dataKey={`${dbId}_throughput`}
                          name={DB_NAMES[dbId]}
                          stroke={getDbColor(dbId)}
                          fill={getDbColor(dbId)}
                          fillOpacity={0.2}
                        />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Метрики транзакций */}
        <TabsContent value="transactions" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {testConfig.databases.map((dbId) => {
              const result = getResultForDb(dbId)
              const txMetrics = result?.transactionMetrics
              const total = txMetrics?.totalTransactions || 0
              const successful = txMetrics?.successfulTransactions || 0
              const failed = txMetrics?.failedTransactions || 0
              const successRate = total > 0 ? ((successful / total) * 100).toFixed(1) : "0"
              
              return (
                <Card key={dbId} className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-foreground">
                      <Database className="h-5 w-5" style={{ color: getDbColor(dbId) }} />
                      {DB_NAMES[dbId]}
                    </CardTitle>
                    <CardDescription>Статистика транзакций</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Всего транзакций</span>
                      <span className="font-mono text-lg text-foreground">{total}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        Успешные
                      </span>
                      <span className="font-mono text-lg text-green-500">{successful}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-2 text-muted-foreground">
                        <XCircle className="h-4 w-4 text-red-500" />
                        Неудачные
                      </span>
                      <span className="font-mono text-lg text-red-500">{failed}</span>
                    </div>
                    <div className="flex justify-between items-center pt-2 border-t border-border">
                      <span className="text-muted-foreground">Успешность</span>
                      <span className="font-mono text-lg text-foreground">{successRate}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Откаты</span>
                      <span className="font-mono text-lg text-foreground">{txMetrics?.rollbacks || 0}</span>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>

          {/* Сравнительная диаграмма */}
          {currentTest?.results && currentTest.results.length > 0 && (
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-foreground">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  Сравнение транзакций
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart 
                      data={currentTest.results.map(r => ({
                        name: DB_NAMES[r.databaseId] || r.databaseId,
                        successful: r.transactionMetrics?.successfulTransactions || 0,
                        failed: r.transactionMetrics?.failedTransactions || 0,
                      }))}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="name" 
                        stroke={CHART_COLORS.axis}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <YAxis 
                        stroke={CHART_COLORS.axis}
                        tick={{ fill: CHART_COLORS.text }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          border: "1px solid hsl(var(--border))",
                          borderRadius: "8px",
                          color: CHART_COLORS.text,
                        }}
                        labelStyle={{ color: CHART_COLORS.text }}
                      />
                      <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                      <Bar dataKey="successful" name="Успешные" fill={CHART_COLORS.success} />
                      <Bar dataKey="failed" name="Неудачные" fill={CHART_COLORS.error} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Внутренние метрики СУБД */}
        <TabsContent value="dbms" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {testConfig.databases.map((dbId) => {
              const result = getResultForDb(dbId)
              const dbmsMetrics = result?.dbmsMetrics
              
              return (
                <Card key={dbId} className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-foreground">
                      <Database className="h-5 w-5" style={{ color: getDbColor(dbId) }} />
                      {DB_NAMES[dbId]} — Внутренние метрики
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-sm text-muted-foreground">Cache Hit Ratio</div>
                        <div className="text-2xl font-mono text-foreground">
                          {dbmsMetrics?.cacheHitRatio?.toFixed(1) || "—"}%
                        </div>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-sm text-muted-foreground">Buffer Pool Hit</div>
                        <div className="text-2xl font-mono text-foreground">
                          {dbmsMetrics?.bufferPoolHitRatio?.toFixed(1) || "—"}%
                        </div>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-sm text-muted-foreground">Ожидание блокировок</div>
                        <div className="text-2xl font-mono text-foreground">
                          {dbmsMetrics?.lockWaits || "—"}
                        </div>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-sm text-muted-foreground">Дедлоки</div>
                        <div className="text-2xl font-mono text-foreground">
                          {dbmsMetrics?.deadlocks || "—"}
                        </div>
                      </div>
                    </div>
                    
                    <div className="pt-4 border-t border-border">
                      <div className="text-sm text-muted-foreground mb-2">Размер БД</div>
                      <div className="text-xl font-mono text-foreground">
                        {dbmsMetrics?.totalDBSizeMB?.toFixed(2) || "—"} MB
                      </div>
                    </div>
                    
                    {dbmsMetrics?.tableSizesMB && Object.keys(dbmsMetrics.tableSizesMB).length > 0 && (
                      <div className="pt-4 border-t border-border">
                        <div className="text-sm text-muted-foreground mb-2">Размеры таблиц (топ-5)</div>
                        <div className="space-y-1">
                          {Object.entries(dbmsMetrics.tableSizesMB)
                            .slice(0, 5)
                            .map(([table, size]) => (
                              <div key={table} className="flex justify-between text-sm">
                                <span className="text-muted-foreground truncate mr-2">{table}</span>
                                <span className="font-mono text-foreground">{size.toFixed(2)} MB</span>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
