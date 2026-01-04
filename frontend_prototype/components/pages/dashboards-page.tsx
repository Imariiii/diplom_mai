"use client"

import { Activity, Clock, Cpu, Database, HardDrive, Zap } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useAppStore } from "@/lib/store"
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
} from "recharts"

const dbColors: Record<string, string> = {
  postgresql: "hsl(var(--chart-1))",
  mysql: "hsl(var(--chart-2))",
  mariadb: "hsl(var(--chart-3))",
  sqlite: "hsl(var(--chart-4))",
  mssql: "hsl(var(--chart-5))",
}

const dbNames: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  mariadb: "MariaDB",
  sqlite: "SQLite",
  mssql: "MS SQL Server",
}

export function DashboardsPage() {
  const { currentTest, realtimeData, testConfig } = useAppStore()

  const chartData = Object.entries(realtimeData).reduce<Record<string, unknown>[]>((acc, [dbId, points]) => {
    points.forEach((point, index) => {
      if (!acc[index]) {
        acc[index] = { time: new Date(point.timestamp).toLocaleTimeString("ru") }
      }
      acc[index][`${dbId}_responseTime`] = point.responseTime.toFixed(2)
      acc[index][`${dbId}_throughput`] = point.throughput.toFixed(0)
      acc[index][`${dbId}_cpu`] = point.cpuUsage.toFixed(1)
      acc[index][`${dbId}_memory`] = point.memoryUsage.toFixed(1)
    })
    return acc
  }, [])

  const getLatestMetric = (dbId: string, metric: keyof (typeof realtimeData)[string][number]) => {
    const points = realtimeData[dbId]
    if (!points || points.length === 0) return "—"
    const value = points[points.length - 1][metric]
    return typeof value === "number" ? value.toFixed(2) : value
  }

  if (!currentTest && Object.keys(realtimeData).length === 0) {
    return (
      <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Card className="bg-card border-border max-w-md">
          <CardHeader className="text-center">
            <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <CardTitle>Нет активных тестов</CardTitle>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Дашборды</h1>
          <p className="text-muted-foreground">Мониторинг производительности в реальном времени</p>
        </div>
        {currentTest && (
          <Badge variant={currentTest.status === "running" ? "default" : "secondary"}>
            {currentTest.status === "running" ? "Выполняется" : "Завершён"}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {testConfig.databases.map((dbId) => (
          <Card key={dbId} className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Database className="h-4 w-4" style={{ color: dbColors[dbId] }} />
                {dbNames[dbId]}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Время отклика</span>
                <span className="font-mono">{getLatestMetric(dbId, "responseTime")} ms</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Пропускная способность</span>
                <span className="font-mono">{getLatestMetric(dbId, "throughput")} req/s</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" />
              Время отклика (ms)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  {testConfig.databases.map((dbId) => (
                    <Line
                      key={dbId}
                      type="monotone"
                      dataKey={`${dbId}_responseTime`}
                      name={dbNames[dbId]}
                      stroke={dbColors[dbId]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Пропускная способность (req/s)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  {testConfig.databases.map((dbId) => (
                    <Area
                      key={dbId}
                      type="monotone"
                      dataKey={`${dbId}_throughput`}
                      name={dbNames[dbId]}
                      stroke={dbColors[dbId]}
                      fill={dbColors[dbId]}
                      fillOpacity={0.2}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-primary" />
              Использование CPU (%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  {testConfig.databases.map((dbId) => (
                    <Line
                      key={dbId}
                      type="monotone"
                      dataKey={`${dbId}_cpu`}
                      name={dbNames[dbId]}
                      stroke={dbColors[dbId]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5 text-primary" />
              Использование памяти (%)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  {testConfig.databases.map((dbId) => (
                    <Line
                      key={dbId}
                      type="monotone"
                      dataKey={`${dbId}_memory`}
                      name={dbNames[dbId]}
                      stroke={dbColors[dbId]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
