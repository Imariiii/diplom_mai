"use client"

import { FileText, TrendingUp, TrendingDown, Minus, Award, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
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
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Cell,
} from "recharts"

export function ReportsPage() {
  const { testHistory, currentTest } = useAppStore()

  const latestTest = currentTest?.status === "completed" ? currentTest : testHistory[testHistory.length - 1]

  // Вычисляем длительность теста
  const getTestDuration = () => {
    // Если сервер прислал итоговую длительность, используем её (согласованно с историей тестов)
    if (latestTest?.summary?.total_duration) {
      return Math.round(latestTest.summary.total_duration)
    }

    if (latestTest?.endTime && latestTest?.startTime) {
      const durationMs = new Date(latestTest.endTime).getTime() - new Date(latestTest.startTime).getTime()
      return Math.round(durationMs / 1000) // в секундах
    }
    return null
  }
  
  const testDuration = getTestDuration()
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return mins > 0 ? `${mins} мин ${secs} сек` : `${secs} сек`
  }

  if (!latestTest || !latestTest.results) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Card className="bg-card border-border max-w-md">
          <CardHeader className="text-center">
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <CardTitle>Нет доступных отчётов</CardTitle>
            <CardDescription>Завершите тестирование для получения отчёта с анализом результатов</CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  const comparisonData = latestTest.results.map((result) => ({
    name: DB_NAMES[result.databaseId],
    "Ср. время отклика": result.metrics.avgResponseTime,
    "Макс. время отклика": result.metrics.maxResponseTime,
    P95: result.metrics.p95ResponseTime,
    P99: result.metrics.p99ResponseTime,
    color: getDbColor(result.databaseId),
  }))

  const throughputData = latestTest.results.map((result) => ({
    name: DB_NAMES[result.databaseId],
    throughput: result.metrics.throughput,
    color: getDbColor(result.databaseId),
  }))

  const radarData = [
    {
      metric: "Скорость",
      ...Object.fromEntries(latestTest.results.map((r) => [DB_NAMES[r.databaseId], 100 - r.metrics.avgResponseTime])),
    },
    {
      metric: "Пропускная способность",
      ...Object.fromEntries(latestTest.results.map((r) => [DB_NAMES[r.databaseId], r.metrics.throughput / 15])),
    },
    {
      metric: "Стабильность",
      ...Object.fromEntries(latestTest.results.map((r) => [DB_NAMES[r.databaseId], 100 - r.metrics.errorRate * 10])),
    },
    {
      metric: "P95 Latency",
      ...Object.fromEntries(latestTest.results.map((r) => [DB_NAMES[r.databaseId], 100 - r.metrics.p95ResponseTime])),
    },
    {
      metric: "P99 Latency",
      ...Object.fromEntries(latestTest.results.map((r) => [DB_NAMES[r.databaseId], 100 - r.metrics.p99ResponseTime])),
    },
  ]

  // Определяем лучшую СУБД (если есть результаты)
  const bestDb = latestTest.results.length > 0
    ? latestTest.results.reduce((best, current) => {
        const bestScore = best.metrics.avgResponseTime + best.metrics.errorRate * 10
        const currentScore = current.metrics.avgResponseTime + current.metrics.errorRate * 10
        return currentScore < bestScore ? current : best
      })
    : null

  const getPerformanceIcon = (db: string) => {
    const result = latestTest.results?.find((r) => r.databaseId === db)
    if (!result) return <Minus className="h-4 w-4" />
    
    // Если нет лучшей БД (нет результатов), возвращаем нейтральную иконку
    if (!bestDb) return <Minus className="h-4 w-4 text-muted-foreground" />

    if (result.databaseId === bestDb.databaseId) {
      return <TrendingUp className="h-4 w-4 text-primary" />
    }

    const diff =
      ((result.metrics.avgResponseTime - bestDb.metrics.avgResponseTime) / bestDb.metrics.avgResponseTime) * 100

    if (diff > 30) return <TrendingDown className="h-4 w-4 text-destructive" />
    return <Minus className="h-4 w-4 text-muted-foreground" />
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Отчёты</h1>
        <p className="text-muted-foreground">Анализ и сравнение результатов тестирования</p>
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{latestTest.name}</CardTitle>
              <CardDescription>
                {latestTest.startTime.toLocaleString("ru")} • Длительность: {testDuration ? formatDuration(testDuration) : "N/A"}
              </CardDescription>
            </div>
            {bestDb && (
              <Badge className="bg-primary/10 text-primary border-primary/20">
                <Award className="h-3 w-3 mr-1" />
                Лучший: {DB_NAMES[bestDb.databaseId]}
              </Badge>
            )}
          </div>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {latestTest.results.map((result) => (
          <Card key={result.databaseId} className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <span style={{ color: getDbColor(result.databaseId) }}>{DB_NAMES[result.databaseId]}</span>
                  {bestDb && result.databaseId === bestDb.databaseId && <Award className="h-4 w-4 text-primary" />}
                </CardTitle>
                {getPerformanceIcon(result.databaseId)}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-muted-foreground">Ср. время отклика</p>
                  <p className="font-mono font-semibold">{result.metrics.avgResponseTime.toFixed(2)} ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Макс. время отклика</p>
                  <p className="font-mono font-semibold">{result.metrics.maxResponseTime.toFixed(2)} ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Пропускная способность</p>
                  <p className="font-mono font-semibold">{result.metrics.throughput.toFixed(0)} req/s</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Ошибки</p>
                  <p className={`font-mono font-semibold ${result.metrics.errorRate > 1 ? "text-destructive" : ""}`}>
                    {result.metrics.errorRate.toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">P95</p>
                  <p className="font-mono font-semibold">{result.metrics.p95ResponseTime.toFixed(2)} ms</p>
                </div>
                <div>
                  <p className="text-muted-foreground">P99</p>
                  <p className="font-mono font-semibold">{result.metrics.p99ResponseTime.toFixed(2)} ms</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Сравнение времени отклика</CardTitle>
            <CardDescription>Средние показатели и процентили (ms)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparisonData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis 
                    type="number" 
                    stroke={CHART_COLORS.axis} 
                    fontSize={12}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    stroke={CHART_COLORS.axis}
                    fontSize={12}
                    width={100}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                    itemStyle={{ color: "hsl(var(--foreground))" }}
                    labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                  />
                  <Legend wrapperStyle={{ color: CHART_COLORS.text, paddingTop: "10px" }} />
                  <Bar dataKey="Ср. время отклика" name="Среднее" fill={METRIC_COLORS.avg}>
                    {comparisonData.map((entry, index) => (
                      <Cell key={`cell-avg-${index}`} fill={METRIC_COLORS.avg} />
                    ))}
                  </Bar>
                  <Bar dataKey="P95" name="P95" fill={METRIC_COLORS.p95}>
                    {comparisonData.map((entry, index) => (
                      <Cell key={`cell-p95-${index}`} fill={METRIC_COLORS.p95} />
                    ))}
                  </Bar>
                  <Bar dataKey="P99" name="P99" fill={METRIC_COLORS.p99}>
                    {comparisonData.map((entry, index) => (
                      <Cell key={`cell-p99-${index}`} fill={METRIC_COLORS.p99} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Пропускная способность</CardTitle>
            <CardDescription>Количество запросов в секунду</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={throughputData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis 
                    dataKey="name" 
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
                    }}
                    itemStyle={{ color: "hsl(var(--foreground))" }}
                    labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
                  />
                  <Bar dataKey="throughput" name="req/s">
                    {throughputData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border lg:col-span-2">
          <CardHeader>
            <CardTitle>Радарный анализ производительности</CardTitle>
            <CardDescription>Комплексное сравнение по ключевым метрикам</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="hsl(var(--border))" />
                  <PolarAngleAxis 
                    dataKey="metric" 
                    stroke={CHART_COLORS.axis} 
                    fontSize={12}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  <PolarRadiusAxis 
                    stroke={CHART_COLORS.axis} 
                    fontSize={10}
                    tick={{ fill: CHART_COLORS.text }}
                  />
                  {latestTest.results.map((result) => (
                    <Radar
                      key={result.databaseId}
                      name={DB_NAMES[result.databaseId]}
                      dataKey={DB_NAMES[result.databaseId]}
                      stroke={getDbColor(result.databaseId)}
                      fill={getDbColor(result.databaseId)}
                      fillOpacity={0.2}
                    />
                  ))}
                  <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {latestTest.results.some((r) => r.metrics.errorRate > 1) && (
        <Card className="bg-destructive/10 border-destructive/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Предупреждения
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {latestTest.results
                .filter((r) => r.metrics.errorRate > 1)
                .map((r) => (
                  <li key={r.databaseId}>
                    {DB_NAMES[r.databaseId]}: высокий процент ошибок ({r.metrics.errorRate.toFixed(2)}%)
                  </li>
                ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
