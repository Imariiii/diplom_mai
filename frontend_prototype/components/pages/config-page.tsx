"use client"

import { useState } from "react"
import { Play, Database, Users, Clock, FileCode, HardDrive } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { useAppStore } from "@/lib/store"
import type { TestRun, TimeSeriesPoint } from "@/lib/types"

const databases = [
  { id: "postgresql", name: "PostgreSQL", type: "postgresql" as const },
  { id: "mysql", name: "MySQL", type: "mysql" as const },
  { id: "mariadb", name: "MariaDB", type: "mariadb" as const },
  { id: "sqlite", name: "SQLite", type: "sqlite" as const },
  { id: "mssql", name: "MS SQL Server", type: "mssql" as const },
]

const queryTypeOptions = [
  { value: "read", label: "Чтение (SELECT)" },
  { value: "write", label: "Запись (INSERT/UPDATE)" },
  { value: "mixed", label: "Смешанный" },
]

const dataSizeOptions = [
  { value: "small", label: "Малый (10K записей)" },
  { value: "medium", label: "Средний (100K записей)" },
  { value: "large", label: "Большой (1M записей)" },
]

export function ConfigPage() {
  const {
    testConfig,
    setTestConfig,
    setCurrentTest,
    addTestToHistory,
    setCurrentPage,
    addRealtimeData,
    clearRealtimeData,
  } = useAppStore()
  const [isRunning, setIsRunning] = useState(false)

  const handleDatabaseToggle = (dbId: string) => {
    const newDatabases = testConfig.databases.includes(dbId)
      ? testConfig.databases.filter((id) => id !== dbId)
      : [...testConfig.databases, dbId]
    setTestConfig({ databases: newDatabases })
  }

  const handleQueryTypeToggle = (type: "read" | "write" | "mixed") => {
    const newTypes = testConfig.queryTypes.includes(type)
      ? testConfig.queryTypes.filter((t) => t !== type)
      : [...testConfig.queryTypes, type]
    if (newTypes.length > 0) {
      setTestConfig({ queryTypes: newTypes })
    }
  }

  const simulateTest = () => {
    if (testConfig.databases.length === 0) return

    setIsRunning(true)
    clearRealtimeData()

    const testRun: TestRun = {
      id: Date.now().toString(),
      name: `Тест ${new Date().toLocaleString("ru")}`,
      status: "running",
      startTime: new Date(),
      config: { ...testConfig },
    }

    setCurrentTest(testRun)
    setCurrentPage("dashboards")

    // Симуляция данных в реальном времени
    let elapsed = 0
    const interval = setInterval(() => {
      elapsed += 1

      testConfig.databases.forEach((dbId) => {
        const baseResponseTime =
          dbId === "postgresql" ? 15 : dbId === "mysql" ? 18 : dbId === "mariadb" ? 17 : dbId === "sqlite" ? 8 : 25
        const point: TimeSeriesPoint = {
          timestamp: Date.now(),
          responseTime: baseResponseTime + Math.random() * 10 - 5,
          throughput: 800 + Math.random() * 400,
          activeConnections: Math.floor(testConfig.concurrentUsers * (0.7 + Math.random() * 0.3)),
          cpuUsage: 30 + Math.random() * 40,
          memoryUsage: 40 + Math.random() * 30,
        }
        addRealtimeData(dbId, point)
      })

      if (elapsed >= testConfig.testDuration) {
        clearInterval(interval)
        setIsRunning(false)

        const completedTest: TestRun = {
          ...testRun,
          status: "completed",
          endTime: new Date(),
          results: testConfig.databases.map((dbId) => ({
            databaseId: dbId,
            metrics: {
              avgResponseTime: 15 + Math.random() * 10,
              maxResponseTime: 50 + Math.random() * 30,
              minResponseTime: 5 + Math.random() * 5,
              throughput: 800 + Math.random() * 400,
              errorRate: Math.random() * 2,
              p95ResponseTime: 35 + Math.random() * 15,
              p99ResponseTime: 45 + Math.random() * 20,
            },
            timeSeriesData: [],
          })),
        }

        setCurrentTest(completedTest)
        addTestToHistory(completedTest)
      }
    }, 1000)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Конфигурация и запуск</h1>
        <p className="text-muted-foreground">Настройте параметры нагрузочного тестирования</p>
      </div>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Выбор СУБД
          </CardTitle>
          <CardDescription>Выберите базы данных для тестирования</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {databases.map((db) => (
              <label
                key={db.id}
                className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  testConfig.databases.includes(db.id)
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <Checkbox
                  checked={testConfig.databases.includes(db.id)}
                  onCheckedChange={() => handleDatabaseToggle(db.id)}
                />
                <span className="font-medium">{db.name}</span>
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            Параллельные пользователи
          </CardTitle>
          <CardDescription>Количество одновременных подключений: {testConfig.concurrentUsers}</CardDescription>
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

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Длительность теста
          </CardTitle>
          <CardDescription>Продолжительность тестирования: {testConfig.testDuration} сек</CardDescription>
        </CardHeader>
        <CardContent>
          <Slider
            value={[testConfig.testDuration]}
            onValueChange={([value]) => setTestConfig({ testDuration: value })}
            min={10}
            max={300}
            step={10}
            className="w-full"
          />
          <div className="flex justify-between text-sm text-muted-foreground mt-2">
            <span>10 сек</span>
            <span>150 сек</span>
            <span>300 сек</span>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5 text-primary" />
            Типы запросов
          </CardTitle>
          <CardDescription>Выберите типы SQL-запросов для тестирования</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            {queryTypeOptions.map((option) => (
              <label
                key={option.value}
                className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                  testConfig.queryTypes.includes(option.value as "read" | "write" | "mixed")
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <Checkbox
                  checked={testConfig.queryTypes.includes(option.value as "read" | "write" | "mixed")}
                  onCheckedChange={() => handleQueryTypeToggle(option.value as "read" | "write" | "mixed")}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5 text-primary" />
            Размер данных
          </CardTitle>
          <CardDescription>Объём тестовых данных в базе</CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={testConfig.dataSize}
            onValueChange={(value) => setTestConfig({ dataSize: value as "small" | "medium" | "large" })}
            className="grid grid-cols-1 sm:grid-cols-3 gap-4"
          >
            {dataSizeOptions.map((option) => (
              <Label
                key={option.value}
                className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  testConfig.dataSize === option.value
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <RadioGroupItem value={option.value} />
                <span>{option.label}</span>
              </Label>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      <Button
        size="lg"
        className="w-full"
        onClick={simulateTest}
        disabled={testConfig.databases.length === 0 || isRunning}
      >
        <Play className="mr-2 h-5 w-5" />
        {isRunning ? "Тест выполняется..." : "Запустить тестирование"}
      </Button>
    </div>
  )
}
