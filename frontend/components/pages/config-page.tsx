"use client"

import { useState, useEffect } from "react"
import { Play, Database, Users, Clock, FileCode, AlertCircle, CheckCircle2, Gauge, Layers, Code, Edit3 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useAppStore } from "@/lib/store"
import { apiClient, type Query } from "@/lib/api"
import { toast } from "sonner"
import type { TestRun, TestScenario, ScenarioConfig, TestMode, Scenario } from "@/lib/types"
import { DatabaseStatePanel } from "@/components/database-state-panel"

const databases = [
  { id: "mysql", name: "MySQL (Sakila)", type: "mysql" as const },
  { id: "postgresql", name: "PostgreSQL (Pagila)", type: "postgresql" as const },
]

const testModes: { id: TestMode; name: string; description: string; icon: React.ElementType }[] = [
  { 
    id: "scenario", 
    name: "По сценарию", 
    description: "Выбор предустановленного сценария нагрузки",
    icon: Layers
  },
  { 
    id: "custom_query", 
    name: "Конкретный запрос", 
    description: "Выбор SQL-запроса из списка или ввод своего",
    icon: Code
  },
]

// Сценарии загружаются из API
const scenarioTypeLabels: Record<string, string> = {
  "read_only": "Только чтение",
  "write_only": "Только запись", 
  "mixed_light": "TPC-C (лёгкий)",
  "mixed_heavy": "Смешанный (тяжёлый)",
  "oltp": "OLTP",
  "olap": "OLAP",
  "custom": "Пользовательский"
}

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
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [scenariosLoading, setScenariosLoading] = useState(true)
  const [healthStatus, setHealthStatus] = useState<{ mysql: boolean; postgresql: boolean }>({
    mysql: false,
    postgresql: false,
  })
  const [useCustomSql, setUseCustomSql] = useState(false)

  useEffect(() => {
    // Загрузка запросов
    apiClient
      .getQueries()
      .then((data) => {
        setQueries(data)
        if (data.length > 0 && !testConfig.selectedQueryId) {
          setTestConfig({ selectedQueryId: data[0].id })
        }
      })
      .catch((error) => {
        console.error("Ошибка загрузки запросов:", error)
        toast.error("Не удалось загрузить список запросов")
      })

    // Загрузка сценариев из БД
    apiClient
      .getEnabledScenarios()
      .then((response) => {
        const scenariosList = response?.scenarios || []
        setScenarios(scenariosList)
        setScenariosLoading(false)
        // Если сценарий не выбран, выбираем первый
        if (scenariosList.length > 0 && !testConfig.scenario) {
          setTestConfig({ scenario: scenariosList[0].id })
        }
      })
      .catch((error) => {
        console.error("Ошибка загрузки сценариев:", error)
        toast.error("Не удалось загрузить сценарии")
        setScenariosLoading(false)
      })

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

  const validateConfig = (): boolean => {
    if (testConfig.databases.length === 0) {
      toast.error("Выберите хотя бы одну базу данных")
      return false
    }

    if (testConfig.testMode === "custom_query") {
      if (useCustomSql) {
        if (!testConfig.customSql.trim()) {
          toast.error("Введите SQL-запрос")
          return false
        }
      } else {
        if (!testConfig.selectedQueryId) {
          toast.error("Выберите запрос из списка")
          return false
        }
      }
    }

    return true
  }

  const runTest = async () => {
    if (!validateConfig()) return

    setIsRunning(true)

    try {
      const testName = `Тест ${new Date().toLocaleString("ru")}`
      
      if (testConfig.testMode === "scenario") {
        const selectedScenario = scenarios.find(s => s.id === testConfig.scenario)
        toast.info(`Запуск тестирования: ${selectedScenario?.name}`)
      } else {
        const queryDesc = useCustomSql 
          ? "пользовательский запрос" 
          : queries.find(q => q.id === testConfig.selectedQueryId)?.name || "выбранный запрос"
        toast.info(`Запуск тестирования: ${queryDesc}`)
      }

      const asyncResponse = await apiClient.runAsyncTest({
        db_types: testConfig.databases,
        iterations: testConfig.iterations,
        virtual_users: testConfig.virtualUsers,
        scenario: testConfig.testMode === "scenario" ? testConfig.scenario : "custom",
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

  const selectedScenario = scenarios?.find(s => s.id === testConfig.scenario)
  const selectedQuery = queries?.find(q => q.id === testConfig.selectedQueryId)

  const canRunTest = () => {
    if (testConfig.databases.length === 0) return false
    if (testConfig.testMode === "custom_query") {
      if (useCustomSql) {
        return testConfig.customSql.trim().length > 0
      }
      return !!testConfig.selectedQueryId
    }
    return true
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

      {/* Режим тестирования */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            Режим тестирования
          </CardTitle>
          <CardDescription>Выберите способ проведения нагрузочного теста</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {testModes.map((mode) => {
              const Icon = mode.icon
              const isSelected = testConfig.testMode === mode.id
              return (
                <label
                  key={mode.id}
                  className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-muted-foreground"
                  }`}
                >
                  <input
                    type="radio"
                    name="testMode"
                    checked={isSelected}
                    onChange={() => setTestConfig({ testMode: mode.id })}
                    className="mt-1"
                  />
                  <div>
                    <div className="flex items-center gap-2 font-medium">
                      <Icon className="h-4 w-4" />
                      {mode.name}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {mode.description}
                    </div>
                  </div>
                </label>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Сценарий тестирования - показывается только в режиме scenario */}
      {testConfig.testMode === "scenario" && (
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
                {(scenarios || []).map((scenario) => (
                  <SelectItem key={scenario.id} value={scenario.id}>
                    <div className="flex flex-col">
                      <span>{scenario.name}</span>
                      <span className="text-xs text-muted-foreground">{scenario.description}</span>
                    </div>
                  </SelectItem>
                ))}
                {(scenarios || []).length === 0 && (
                  <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                    Нет доступных сценариев
                  </div>
                )}
              </SelectContent>
            </Select>
            
            {selectedScenario && (
              <div className="p-4 bg-muted rounded-lg space-y-2">
                <div className="font-medium">{selectedScenario.name || 'Без названия'}</div>
                <div className="text-sm text-muted-foreground">{selectedScenario.description || 'Нет описания'}</div>
                <div className="flex gap-4 text-sm flex-wrap">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                    <span>Запросов: {selectedScenario.queries_count ?? selectedScenario.queries?.length ?? 0}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                    <span>Тип: {selectedScenario.scenario_type || 'custom'}</span>
                  </div>
                  {selectedScenario.is_builtin && (
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                      <span>Системный</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Конкретный запрос - показывается только в режиме custom_query */}
      {testConfig.testMode === "custom_query" && (
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileCode className="h-5 w-5 text-primary" />
              SQL-запрос для тестирования
            </CardTitle>
            <CardDescription>Выберите запрос из списка или введите свой</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Переключатель между списком и своим запросом */}
            <div className="flex gap-2">
              <Button
                variant={!useCustomSql ? "default" : "outline"}
                size="sm"
                onClick={() => setUseCustomSql(false)}
              >
                <FileCode className="h-4 w-4 mr-2" />
                Из списка
              </Button>
              <Button
                variant={useCustomSql ? "default" : "outline"}
                size="sm"
                onClick={() => setUseCustomSql(true)}
              >
                <Edit3 className="h-4 w-4 mr-2" />
                Свой запрос
              </Button>
            </div>

            {!useCustomSql ? (
              <>
                <Select 
                  value={testConfig.selectedQueryId} 
                  onValueChange={(value) => setTestConfig({ selectedQueryId: value })}
                >
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
                  <div className="p-3 bg-muted rounded-lg">
                    <div className="text-sm text-muted-foreground mb-2">{selectedQuery.description}</div>
                    <pre className="text-sm overflow-x-auto font-mono">
                      {selectedQuery.sql}
                    </pre>
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-2">
                <Textarea
                  placeholder="Введите SQL-запрос для тестирования..."
                  value={testConfig.customSql}
                  onChange={(e) => setTestConfig({ customSql: e.target.value })}
                  className="font-mono min-h-[120px]"
                />
                <div className="text-xs text-muted-foreground">
                  Поддерживаются SQL-запросы, совместимые с выбранными СУБД
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

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

      {/* Панель управления состоянием БД */}
      <DatabaseStatePanel />

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
              <span className="text-muted-foreground">Режим:</span>
              <span className="ml-2 font-medium">
                {testConfig.testMode === "scenario" ? "По сценарию" : "Конкретный запрос"}
              </span>
            </div>
            {testConfig.testMode === "scenario" ? (
              <div>
                <span className="text-muted-foreground">Сценарий:</span>
                <span className="ml-2 font-medium">{selectedScenario?.name || "Не выбрано"}</span>
              </div>
            ) : (
              <>
                <div>
                  <span className="text-muted-foreground">Запрос:</span>
                  <span className="ml-2 font-medium">
                    {useCustomSql 
                      ? "Пользовательский SQL" 
                      : (selectedQuery?.name || "Не выбрано")}
                  </span>
                </div>
              </>
            )}
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
        disabled={!canRunTest() || isRunning}
      >
        <Play className="mr-2 h-5 w-5" />
        {isRunning ? "Тест выполняется..." : "Запустить тестирование"}
      </Button>
    </div>
  )
}
