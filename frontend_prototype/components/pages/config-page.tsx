"use client"

import { useState, useEffect } from "react"
import { Play, Database, Users, Clock, FileCode, AlertCircle, CheckCircle2, Gauge, Timer, Layers } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAppStore } from "@/lib/store"
import { apiClient, type Query } from "@/lib/api"
import { toast } from "sonner"
import type { TestRun, TestScenario, ScenarioConfig } from "@/lib/types"

const databases = [
  { id: "mysql", name: "MySQL (Sakila)", type: "mysql" as const },
  { id: "postgresql", name: "PostgreSQL (Pagila)", type: "postgresql" as const },
]

// Сценарии нагрузочного тестирования
const scenarios: ScenarioConfig[] = [
  { 
    id: "read_only", 
    name: "Только чтение", 
    description: "100% SELECT запросы",
    readPercent: 100,
    writePercent: 0
  },
  { 
    id: "mixed_light", 
    name: "TPC-C (лёгкий)", 
    description: "80% SELECT, 20% UPDATE",
    readPercent: 80,
    writePercent: 20
  },
  { 
    id: "mixed_heavy", 
    name: "Смешанный (тяжёлый)", 
    description: "50% SELECT, 50% UPDATE",
    readPercent: 50,
    writePercent: 50
  },
  { 
    id: "write_only", 
    name: "Только запись", 
    description: "100% INSERT/UPDATE/DELETE",
    readPercent: 0,
    writePercent: 100
  },
  { 
    id: "oltp", 
    name: "OLTP", 
    description: "Транзакционная нагрузка",
    readPercent: 70,
    writePercent: 30
  },
  { 
    id: "olap", 
    name: "OLAP", 
    description: "Аналитические запросы",
    readPercent: 95,
    writePercent: 5
  },
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
      const selectedScenario = scenarios.find(s => s.id === testConfig.scenario)
      const testName = `Тест ${new Date().toLocaleString("ru")}`
      
      toast.info(`Запуск тестирования: ${selectedScenario?.name || testConfig.scenario}`)

      // Асинхронный запуск теста с WebSocket
      const asyncResponse = await apiClient.runAsyncTest({
        db_types: testConfig.databases,
        iterations: testConfig.iterations,
        duration: testConfig.testDuration,
        virtual_users: testConfig.virtualUsers,
        scenario: testConfig.scenario,
        warmup_time: testConfig.warmupTime,
        test_name: testName,
      })

      const testRun: TestRun = {
        id: asyncResponse.test_id,
        name: asyncResponse.name,
        status: "running",
        startTime: new Date(),
        config: { ...testConfig },
      }

      setCurrentTest(testRun)
      setCurrentPage("dashboards")
      
      toast.success(`Тест запущен! ID: ${asyncResponse.test_id}`)
      toast.info("Подключение к real-time обновлениям...")

    } catch (error) {
      console.error("Ошибка запуска теста:", error)
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
      setIsRunning(false)
    }
  }

  // Fallback для синхронного запуска (если WebSocket недоступен)
  const runTestSync = async () => {
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

      const selectedScenario = scenarios.find(s => s.id === testConfig.scenario)
      toast.info(`Запуск тестирования: ${selectedScenario?.name || testConfig.scenario}`)

      // Запуск полного набора тестов
      const response = await apiClient.runFullTest({
        db_types: testConfig.databases,
        iterations: testConfig.iterations,
        duration: testConfig.testDuration,
        virtual_users: testConfig.virtualUsers,
        scenario: testConfig.scenario,
        warmup_time: testConfig.warmupTime,
      })

      // Агрегируем результаты по СУБД
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
        const sortedTimes = [...aggregated.times].sort((a, b) => a - b)
        const avgTime = aggregated.times.reduce((a, b) => a + b, 0) / aggregated.times.length
        const maxTime = Math.max(...aggregated.maxTimes)
        const minTime = Math.min(...aggregated.minTimes)
        const errorRate = (aggregated.totalFailed / aggregated.totalIterations) * 100
        
        // Вычисление перцентилей
        const p50Index = Math.floor(sortedTimes.length * 0.5)
        const p95Index = Math.floor(sortedTimes.length * 0.95)
        const p99Index = Math.floor(sortedTimes.length * 0.99)

        return {
          databaseId: dbType,
          databaseName: dbType === "mysql" ? "MySQL" : "PostgreSQL",
          metrics: {
            avgResponseTime: avgTime,
            p50ResponseTime: sortedTimes[p50Index] || avgTime,
            p95ResponseTime: sortedTimes[p95Index] || avgTime * 1.5,
            p99ResponseTime: sortedTimes[p99Index] || avgTime * 2,
            minResponseTime: minTime,
            maxResponseTime: maxTime,
            tps: aggregated.totalSuccessful / (testConfig.testDuration || 60),
            throughput: 1000 / avgTime,
            activeConnections: testConfig.virtualUsers,
            errorCount: aggregated.totalFailed,
            errorRate: errorRate,
          },
          transactionMetrics: {
            totalTransactions: aggregated.totalIterations,
            successfulTransactions: aggregated.totalSuccessful,
            failedTransactions: aggregated.totalFailed,
            rollbacks: 0,
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

  const selectedScenario = scenarios.find(s => s.id === testConfig.scenario)

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

      {/* Выбор СУБД */}
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

      {/* Сценарий тестирования */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            Сценарий тестирования
          </CardTitle>
          <CardDescription>Выберите тип нагрузки для теста</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select 
            value={testConfig.scenario} 
            onValueChange={(value: TestScenario) => setTestConfig({ scenario: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Выберите сценарий" />
            </SelectTrigger>
            <SelectContent>
              {scenarios.map((scenario) => (
                <SelectItem key={scenario.id} value={scenario.id}>
                  <div className="flex flex-col">
                    <span>{scenario.name}</span>
                    <span className="text-xs text-muted-foreground">{scenario.description}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          {selectedScenario && (
            <div className="p-4 bg-muted rounded-lg space-y-2">
              <div className="font-medium">{selectedScenario.name}</div>
              <div className="text-sm text-muted-foreground">{selectedScenario.description}</div>
              <div className="flex gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                  <span>SELECT: {selectedScenario.readPercent}%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
                  <span>UPDATE: {selectedScenario.writePercent}%</span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Выбор запроса */}
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

      {/* Длительность теста */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Timer className="h-5 w-5 text-primary" />
            Длительность теста
          </CardTitle>
          <CardDescription>
            Установите продолжительность теста в секундах: {testConfig.testDuration} сек 
            ({Math.floor(testConfig.testDuration / 60)} мин {testConfig.testDuration % 60} сек)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Slider
            value={[testConfig.testDuration]}
            onValueChange={([value]) => setTestConfig({ testDuration: value })}
            min={10}
            max={600}
            step={10}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>10 сек</span>
            <span>5 мин</span>
            <span>10 мин</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[30, 60, 180, 600].map((duration) => (
              <Button
                key={duration}
                variant={testConfig.testDuration === duration ? "default" : "outline"}
                size="sm"
                onClick={() => setTestConfig({ testDuration: duration })}
              >
                {duration < 60 ? `${duration} сек` : `${duration / 60} мин`}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Виртуальные пользователи */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            Виртуальные пользователи
          </CardTitle>
          <CardDescription>
            Количество параллельных соединений: {testConfig.virtualUsers}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Slider
            value={[testConfig.virtualUsers]}
            onValueChange={([value]) => setTestConfig({ virtualUsers: value })}
            min={1}
            max={200}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>1</span>
            <span>100</span>
            <span>200</span>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[10, 50, 100, 200].map((users) => (
              <Button
                key={users}
                variant={testConfig.virtualUsers === users ? "default" : "outline"}
                size="sm"
                onClick={() => setTestConfig({ virtualUsers: users })}
              >
                {users}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Количество итераций */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" />
            Количество итераций
          </CardTitle>
          <CardDescription>
            Количество повторений запроса на пользователя: {testConfig.iterations}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Slider
            value={[testConfig.iterations]}
            onValueChange={([value]) => setTestConfig({ iterations: value })}
            min={1}
            max={1000}
            step={10}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>1</span>
            <span>500</span>
            <span>1000</span>
          </div>
        </CardContent>
      </Card>

      {/* Время прогрева */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Время прогрева
          </CardTitle>
          <CardDescription>
            Период прогрева перед началом сбора метрик: {testConfig.warmupTime} сек
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Slider
            value={[testConfig.warmupTime]}
            onValueChange={([value]) => setTestConfig({ warmupTime: value })}
            min={0}
            max={30}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground mt-2">
            <span>0 сек</span>
            <span>15 сек</span>
            <span>30 сек</span>
          </div>
        </CardContent>
      </Card>

      {/* Сводка конфигурации */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle>Сводка конфигурации</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">СУБД:</span>
              <span className="ml-2 font-medium">
                {testConfig.databases.length > 0 
                  ? testConfig.databases.map(d => databases.find(db => db.id === d)?.name).join(", ")
                  : "Не выбрано"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Сценарий:</span>
              <span className="ml-2 font-medium">{selectedScenario?.name || "Не выбрано"}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Длительность:</span>
              <span className="ml-2 font-medium">{testConfig.testDuration} сек</span>
            </div>
            <div>
              <span className="text-muted-foreground">Виртуальных пользователей:</span>
              <span className="ml-2 font-medium">{testConfig.virtualUsers}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Итераций:</span>
              <span className="ml-2 font-medium">{testConfig.iterations}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Время прогрева:</span>
              <span className="ml-2 font-medium">{testConfig.warmupTime} сек</span>
            </div>
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
