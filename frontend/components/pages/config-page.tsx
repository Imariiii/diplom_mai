"use client"

import { useState, useEffect } from "react"
import { Play, Database, Users, Clock, FileCode, AlertCircle, Gauge, Layers, Code, Edit3 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { useAppStore } from "@/lib/store"
import { apiClient, type Query } from "@/lib/api"
import { toast } from "sonner"
import type { TestRun, TestScenario, ScenarioConfig, TestMode, Scenario, DatabaseConnection } from "@/lib/types"
import { DatabaseStatePanel } from "@/components/database-state-panel"
import { ConnectionManager } from "./config/connection-manager"
import { ConnectionStatusCard } from "./config/connection-status-card"
import { DatabaseSelectionCard } from "./config/database-selection-card"
import { TestModeSelectorCard } from "./config/test-mode-selector-card"
import { ScenarioSelectorCard } from "./config/scenario-selector-card"
import { QuerySelectorCard } from "./config/query-selector-card"
import { SliderConfigCard } from "./config/slider-config-card"
import { ConfigSummaryCard } from "./config/config-summary-card"

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
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [healthStatus, setHealthStatus] = useState<Record<string, boolean>>({})
  const [useCustomSql, setUseCustomSql] = useState(false)

  useEffect(() => {
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

    apiClient
      .getEnabledScenarios()
      .then((response) => {
        const scenariosList = response?.scenarios || []
        setScenarios(scenariosList)
        setScenariosLoading(false)
        if (scenariosList.length > 0 && !testConfig.scenario) {
          setTestConfig({ scenario: scenariosList[0].id })
        }
      })
      .catch((error) => {
        console.error("Ошибка загрузки сценариев:", error)
        toast.error("Не удалось загрузить сценарии")
        setScenariosLoading(false)
      })
  }, [])

  const handleConnectionsChange = (newConnections: DatabaseConnection[]) => {
    setConnections(newConnections)
    const status: Record<string, boolean> = {}
    newConnections.forEach((conn) => {
      status[conn.id] = true
    })
    setHealthStatus(status)
  }

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
        connection_ids: testConfig.databases,
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
        connection_names: testConfig.databases.reduce((acc, dbId) => {
          const conn = connections.find(c => c.id === dbId)
          if (conn) {
            acc[dbId] = conn.name
          }
          return acc
        }, {} as Record<string, string>),
        connection_db_types: testConfig.databases.reduce((acc, dbId) => {
          const conn = connections.find(c => c.id === dbId)
          if (conn) {
            acc[dbId] = conn.dbms_type
          }
          return acc
        }, {} as Record<string, string>),
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

      <ConnectionManager onConnectionsChange={handleConnectionsChange} />

      <ConnectionStatusCard connections={connections} healthStatus={healthStatus} />

      <DatabaseSelectionCard
        connections={connections}
        selectedDatabases={testConfig.databases}
        healthStatus={healthStatus}
        onToggle={handleDatabaseToggle}
      />

      <TestModeSelectorCard
        testMode={testConfig.testMode}
        onModeChange={(mode) => setTestConfig({ testMode: mode })}
      />

      {testConfig.testMode === "scenario" && (
        <ScenarioSelectorCard
          scenarios={scenarios}
          selectedScenarioId={testConfig.scenario}
          onScenarioChange={(id) => setTestConfig({ scenario: id })}
        />
      )}

      {testConfig.testMode === "custom_query" && (
        <QuerySelectorCard
          queries={queries}
          selectedQueryId={testConfig.selectedQueryId}
          useCustomSql={useCustomSql}
          customSql={testConfig.customSql}
          onQueryChange={(id) => setTestConfig({ selectedQueryId: id })}
          onCustomSqlChange={(sql) => setTestConfig({ customSql: sql })}
          onToggleCustom={setUseCustomSql}
        />
      )}

      <SliderConfigCard
        title="Виртуальные пользователи"
        icon={Users}
        value={testConfig.virtualUsers}
        min={1}
        max={200}
        step={1}
        unit=""
        description="Количество параллельных соединений"
        presets={[10, 50, 100, 200]}
        onValueChange={(v) => setTestConfig({ virtualUsers: v })}
      />

      <SliderConfigCard
        title="Количество итераций"
        icon={Gauge}
        value={testConfig.iterations}
        min={1}
        max={1000}
        step={10}
        unit=""
        description="Количество повторений запроса на пользователя"
        onValueChange={(v) => setTestConfig({ iterations: v })}
      />

      <SliderConfigCard
        title="Время прогрева"
        icon={Clock}
        value={testConfig.warmupTime}
        min={0}
        max={30}
        step={1}
        unit=" сек"
        description="Период прогрева перед началом сбора метрик"
        onValueChange={(v) => setTestConfig({ warmupTime: v })}
      />

      <DatabaseStatePanel />

      <ConfigSummaryCard
        selectedDatabases={testConfig.databases}
        testMode={testConfig.testMode}
        selectedScenario={selectedScenario}
        selectedQuery={selectedQuery}
        useCustomSql={useCustomSql}
        virtualUsers={testConfig.virtualUsers}
        iterations={testConfig.iterations}
        warmupTime={testConfig.warmupTime}
      />

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
