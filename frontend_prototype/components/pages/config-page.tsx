"use client"

import { useState, useEffect } from "react"
import { Play, Database, Users, Clock, FileCode, AlertCircle, CheckCircle2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAppStore } from "@/lib/store"
import { apiClient, type Query } from "@/lib/api"
import { toast } from "sonner"
import type { TestRun } from "@/lib/types"

const databases = [
  { id: "mysql", name: "MySQL (Sakila)", type: "mysql" as const },
  { id: "postgresql", name: "PostgreSQL (Pagila)", type: "postgresql" as const },
]

export function ConfigPage() {
  const {
    testConfig,
    setTestConfig,
    setCurrentTest,
    addTestToHistory,
    setCurrentPage,
  } = useAppStore()
  const [isRunning, setIsRunning] = useState(false)
  const [queries, setQueries] = useState<Query[]>([])
  const [selectedQuery, setSelectedQuery] = useState<string>("")
  const [healthStatus, setHealthStatus] = useState<{ mysql: boolean; postgresql: boolean }>({
    mysql: false,
    postgresql: false,
  })

  useEffect(() => {
    // Загрузка списка запросов
    apiClient
      .getQueries()
      .then((data) => {
        setQueries(data)
        if (data.length > 0) {
          setSelectedQuery(data[0].id)
        }
      })
      .catch((error) => {
        console.error("Ошибка загрузки запросов:", error)
        toast.error("Не удалось загрузить список запросов")
      })

    // Проверка статуса подключений
    apiClient
      .getHealth()
      .then((status) => {
        setHealthStatus({
          mysql: status.mysql === "connected",
          postgresql: status.postgresql === "connected",
        })
      })
      .catch((error) => {
        console.error("Ошибка проверки статуса:", error)
      })
  }, [])

  const handleDatabaseToggle = (dbId: string) => {
    const newDatabases = testConfig.databases.includes(dbId)
      ? testConfig.databases.filter((id) => id !== dbId)
      : [...testConfig.databases, dbId]
    setTestConfig({ databases: newDatabases })
  }

  const runTest = async () => {
    if (testConfig.databases.length === 0) {
      toast.error("Выберите хотя бы одну базу данных")
      return
    }

    if (!selectedQuery) {
      toast.error("Выберите запрос для тестирования")
      return
    }

    setIsRunning(true)

    try {
      const testRun: TestRun = {
        id: Date.now().toString(),
        name: `Тест ${new Date().toLocaleString("ru")}`,
        status: "running",
        startTime: new Date(),
        config: { ...testConfig },
      }

      setCurrentTest(testRun)
      setCurrentPage("dashboards")

      toast.info("Запуск тестирования...")

      // Запуск полного набора тестов или одиночного теста
      const response = await apiClient.runFullTest({
        db_types: testConfig.databases,
        iterations: testConfig.concurrentUsers,
      })

      // Агрегируем результаты по СУБД (а не по запросам)
      const dbResults: Record<string, {
        times: number[]
        maxTimes: number[]
        minTimes: number[]
        totalSuccessful: number
        totalFailed: number
        totalIterations: number
      }> = {}

      // Собираем все метрики по каждой СУБД
      response.results.forEach((result) => {
        Object.entries(result.comparison).forEach(([dbType, stats]) => {
          if (!dbResults[dbType]) {
            dbResults[dbType] = {
              times: [],
              maxTimes: [],
              minTimes: [],
              totalSuccessful: 0,
              totalFailed: 0,
              totalIterations: 0,
            }
          }
          if (stats.avg_time_ms !== undefined) {
            dbResults[dbType].times.push(stats.avg_time_ms)
            dbResults[dbType].maxTimes.push(stats.max_time_ms)
            dbResults[dbType].minTimes.push(stats.min_time_ms)
            dbResults[dbType].totalSuccessful += stats.successful
            dbResults[dbType].totalFailed += stats.failed
            dbResults[dbType].totalIterations += stats.iterations
          }
        })
      })

      // Создаем уникальные результаты по СУБД
      const uniqueResults = Object.entries(dbResults).map(([dbType, aggregated]) => {
        const avgTime = aggregated.times.reduce((a, b) => a + b, 0) / aggregated.times.length
        const maxTime = Math.max(...aggregated.maxTimes)
        const minTime = Math.min(...aggregated.minTimes)
        const errorRate = (aggregated.totalFailed / aggregated.totalIterations) * 100

        return {
          databaseId: dbType,
          metrics: {
            avgResponseTime: avgTime,
            maxResponseTime: maxTime,
            minResponseTime: minTime,
            throughput: 1000 / avgTime, // Примерная пропускная способность
            errorRate: errorRate,
            p95ResponseTime: avgTime * 1.5, // Приблизительное значение
            p99ResponseTime: avgTime * 2, // Приблизительное значение
          },
          timeSeriesData: [],
        }
      })

      const completedTest: TestRun = {
        ...testRun,
        status: "completed",
        endTime: new Date(),
        results: uniqueResults,
      }

      setCurrentTest(completedTest)
      addTestToHistory(completedTest)
      toast.success("Тестирование завершено!")

      if (response.charts.comparison || response.charts.statistics) {
        toast.info("Графики и отчеты созданы в папке results/")
      }
    } catch (error) {
      console.error("Ошибка выполнения теста:", error)
      toast.error(`Ошибка: ${error instanceof Error ? error.message : "Неизвестная ошибка"}`)
      
      const failedTest: TestRun = {
        id: Date.now().toString(),
        name: `Тест ${new Date().toLocaleString("ru")}`,
        status: "failed",
        startTime: new Date(),
        endTime: new Date(),
        config: { ...testConfig },
      }
      setCurrentTest(failedTest)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Конфигурация и запуск</h1>
        <p className="text-muted-foreground">Настройте параметры нагрузочного тестирования</p>
      </div>

      {/* Статус подключений */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Статус подключений
          </CardTitle>
          <CardDescription>Проверка доступности баз данных</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {databases.map((db) => {
              const isConnected = healthStatus[db.id as keyof typeof healthStatus]
              return (
                <div
                  key={db.id}
                  className={`flex items-center gap-3 p-4 rounded-lg border ${
                    isConnected ? "border-green-500/50 bg-green-500/10" : "border-red-500/50 bg-red-500/10"
                  }`}
                >
                  {isConnected ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <div className="font-medium">{db.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {isConnected ? "Подключено" : "Не подключено"}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Выбор СУБД
          </CardTitle>
          <CardDescription>Выберите базы данных для тестирования</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {databases.map((db) => {
              const isConnected = healthStatus[db.id as keyof typeof healthStatus]
              return (
                <label
                  key={db.id}
                  className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                    testConfig.databases.includes(db.id)
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-muted-foreground"
                  } ${!isConnected ? "opacity-50" : ""}`}
                >
                  <Checkbox
                    checked={testConfig.databases.includes(db.id)}
                    onCheckedChange={() => handleDatabaseToggle(db.id)}
                    disabled={!isConnected}
                  />
                  <span className="font-medium">{db.name}</span>
                </label>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5 text-primary" />
            Выбор запроса
          </CardTitle>
          <CardDescription>Выберите SQL-запрос для тестирования</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedQuery} onValueChange={setSelectedQuery}>
            <SelectTrigger>
              <SelectValue placeholder="Выберите запрос" />
            </SelectTrigger>
            <SelectContent>
              {queries.map((query) => (
                <SelectItem key={query.id} value={query.id}>
                  {query.name} - {query.description}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedQuery && (
            <div className="mt-4 p-3 bg-muted rounded-lg">
              <pre className="text-sm overflow-x-auto">
                {queries.find((q) => q.id === selectedQuery)?.sql}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            Количество итераций
          </CardTitle>
          <CardDescription>Количество повторений каждого запроса: {testConfig.concurrentUsers}</CardDescription>
        </CardHeader>
        <CardContent>
          <Slider
            value={[testConfig.concurrentUsers]}
            onValueChange={([value]) => setTestConfig({ concurrentUsers: value })}
            min={1}
            max={100}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground mt-2">
            <span>1</span>
            <span>50</span>
            <span>100</span>
          </div>
        </CardContent>
      </Card>

      <Button
        size="lg"
        className="w-full"
        onClick={runTest}
        disabled={testConfig.databases.length === 0 || isRunning || !selectedQuery}
      >
        <Play className="mr-2 h-5 w-5" />
        {isRunning ? "Тест выполняется..." : "Запустить тестирование"}
      </Button>
    </div>
  )
}
