"use client"

import { FileText, TrendingUp, TrendingDown, Minus, Award, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useAppStore } from "@/lib/store"
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

const dbNames: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  mariadb: "MariaDB",
  sqlite: "SQLite",
  mssql: "MS SQL Server",
}

const dbColors: Record<string, string> = {
  postgresql: "#ffffff",
  mysql: "#ffffff",
  mariadb: "hsl(var(--chart-3))",
  sqlite: "hsl(var(--chart-4))",
  mssql: "hsl(var(--chart-5))",
}

export function ReportsPage() {
  const { testHistory, currentTest } = useAppStore()

  const latestTest = currentTest?.status === "completed" ? currentTest : testHistory[testHistory.length - 1]

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
    name: dbNames[result.databaseId],
    "Ср. время отклика": result.metrics.avgResponseTime,
    "Макс. время отклика": result.metrics.maxResponseTime,
    P95: result.metrics.p95ResponseTime,
    P99: result.metrics.p99ResponseTime,
    fill: dbColors[result.databaseId],
  }))

  const throughputData = latestTest.results.map((result) => ({
    name: dbNames[result.databaseId],
    throughput: result.metrics.throughput,
    fill: dbColors[result.databaseId],
  }))

  const radarData = [
    {
      metric: "Скорость",
      ...Object.fromEntries(latestTest.results.map((r) => [dbNames[r.databaseId], 100 - r.metrics.avgResponseTime])),
    },
    {
      metric: "Пропускная способность",
      ...Object.fromEntries(latestTest.results.map((r) => [dbNames[r.databaseId], r.metrics.throughput / 15])),
    },
    {
      metric: "Стабильность",
      ...Object.fromEntries(latestTest.results.map((r) => [dbNames[r.databaseId], 100 - r.metrics.errorRate * 10])),
    },
    {
      metric: "P95 Latency",
      ...Object.fromEntries(latestTest.results.map((r) => [dbNames[r.databaseId], 100 - r.metrics.p95ResponseTime])),
    },
    {
      metric: "P99 Latency",
      ...Object.fromEntries(latestTest.results.map((r) => [dbNames[r.databaseId], 100 - r.metrics.p99ResponseTime])),
    },
  ]

  // Определяем лучшую СУБД
  const bestDb = latestTest.results.reduce((best, current) => {
    const bestScore = best.metrics.avgResponseTime + best.metrics.errorRate * 10
    const currentScore = current.metrics.avgResponseTime + current.metrics.errorRate * 10
    return currentScore < bestScore ? current : best
  })

  const getPerformanceIcon = (db: string) => {
    const result = latestTest.results?.find((r) => r.databaseId === db)
    if (!result) return <Minus className="h-4 w-4" />

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
                {latestTest.startTime.toLocaleString("ru")} • Длительность: {latestTest.config.testDuration} сек
              </CardDescription>
            </div>
            <Badge className="bg-primary/10 text-primary border-primary/20">
              <Award className="h-3 w-3 mr-1" />
              Лучший: {dbNames[bestDb.databaseId]}
            </Badge>
          </div>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {latestTest.results.map((result) => (
          <Card key={result.databaseId} className="bg-card border-border">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  {dbNames[result.databaseId]}
                  {result.databaseId === bestDb.databaseId && <Award className="h-4 w-4 text-primary" />}
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
                    stroke="#ffffff" 
                    fontSize={12}
                    tick={{ fill: "#ffffff" }}
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    stroke="#ffffff"
                    fontSize={12}
                    width={100}
                    tick={{ fill: "#ffffff" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      color: "#ffffff",
                    }}
                    labelStyle={{ color: "#ffffff" }}
                  />
                  <Legend wrapperStyle={{ color: "#ffffff" }} />
                  <Bar dataKey="Ср. время отклика" fill="#ffffff" />
                  <Bar dataKey="P95" fill="#ffffff" />
                  <Bar dataKey="P99" fill="#ffffff" />
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
                    stroke="#ffffff" 
                    fontSize={12}
                    tick={{ fill: "#ffffff" }}
                  />
                  <YAxis
                    stroke="#ffffff" 
                    fontSize={12}
                    tick={{ fill: "#ffffff" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      color: "#ffffff",
                    }}
                    labelStyle={{ color: "#ffffff" }}
                  />
                  <Bar dataKey="throughput" name="req/s">
                    {throughputData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
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
                    stroke="#ffffff" 
                    fontSize={12}
                    tick={{ fill: "#ffffff" }}
                  />
                  <PolarRadiusAxis 
                    stroke="#ffffff" 
                    fontSize={10}
                    tick={{ fill: "#ffffff" }}
                  />
                  {latestTest.results.map((result, index) => (
                    <Radar
                      key={result.databaseId}
                      name={dbNames[result.databaseId]}
                      dataKey={dbNames[result.databaseId]}
                      stroke={dbColors[result.databaseId]}
                      fill={dbColors[result.databaseId]}
                      fillOpacity={0.2}
                    />
                  ))}
                  <Legend wrapperStyle={{ color: "#ffffff" }} />
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
                    {dbNames[r.databaseId]}: высокий процент ошибок ({r.metrics.errorRate.toFixed(2)}%)
                  </li>
                ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
