"use client"

import { useState, useEffect } from "react"
import { Play, Users, Clock, Gauge } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/lib/store"
import { apiClient } from "@/lib/api"
import { toast } from "sonner"
import type {
  TestRun,
  ScenarioTemplate,
  DatabaseConnection,
  LogicalDatabaseWithConnections,
  LogicalDatabaseDetail,
} from "@/lib/types"
import { LogicalDbSelectorCard } from "./config/logical-db-selector-card"
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
    setCurrentPage,
  } = useAppStore()
  const [isRunning, setIsRunning] = useState(false)
  const [scenarios, setScenarios] = useState<ScenarioTemplate[]>([])
  const [scenariosLoading, setScenariosLoading] = useState(true)
  const [logicalDatabases, setLogicalDatabases] = useState<LogicalDatabaseWithConnections[]>([])
  const [selectedLogicalDbId, setSelectedLogicalDbId] = useState<string | null>(null)
  const [selectedLogicalDatabaseDetail, setSelectedLogicalDatabaseDetail] = useState<LogicalDatabaseDetail | null>(null)
  const [healthStatus, setHealthStatus] = useState<Record<string, boolean>>({})

  // Подключения выбранной логической БД
  const connections: DatabaseConnection[] = selectedLogicalDbId
    ? (logicalDatabases.find((db) => db.id === selectedLogicalDbId)?.connections ?? [])
    : []

  useEffect(() => {
    apiClient
      .getScenarioTemplates()
      .then((response) => {
        const scenariosList = response?.templates || []
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

    loadLogicalDatabases()
  }, [])

  const loadLogicalDatabases = () => {
    apiClient
      .getLogicalDatabases()
      .then((response) => {
        const dbs = response.databases
        setLogicalDatabases(dbs)

        // Инициализируем статус всех подключений
        const status: Record<string, boolean> = {}
        dbs.forEach((db) => db.connections.forEach((conn) => { status[conn.id] = true }))
        setHealthStatus(status)

        // Автовыбор первой БД, если она одна
        if (dbs.length === 1 && !selectedLogicalDbId) {
          setSelectedLogicalDbId(dbs[0].id)
        }
      })
      .catch((error) => {
        console.error("Ошибка загрузки логических баз данных:", error)
        toast.error("Не удалось загрузить список баз данных")
      })
  }

  useEffect(() => {
    if (!selectedLogicalDbId) {
      setSelectedLogicalDatabaseDetail(null)
      return
    }

    apiClient
      .getLogicalDatabaseDetail(selectedLogicalDbId)
      .then((detail) => setSelectedLogicalDatabaseDetail(detail))
      .catch(() => setSelectedLogicalDatabaseDetail(null))
  }, [selectedLogicalDbId])

  const handleLogicalDbSelect = (id: string) => {
    if (id === selectedLogicalDbId) return

    setSelectedLogicalDbId(id)

    // Сбрасываем выбранные подключения, если они не принадлежат новой БД
    const newDb = logicalDatabases.find((db) => db.id === id)
    if (newDb) {
      const validIds = new Set(newDb.connections.map((c) => c.id))
      const filtered = testConfig.databases.filter((dbId) => validIds.has(dbId))
      if (filtered.length !== testConfig.databases.length) {
        setTestConfig({ databases: filtered })
      }
    }
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

    const selectedConnections = connections.filter((connection) =>
      testConfig.databases.includes(connection.id)
    )
    const missingProfiles = selectedConnections.filter((connection) => !connection.schema_profile_id)
    if (missingProfiles.length > 0) {
      toast.error("Для выбранных БД сначала подтвердите schema profile")
      return false
    }

    const distinctProfiles = new Set(
      selectedConnections
        .map((connection) => connection.schema_profile_id)
        .filter((value): value is string => Boolean(value))
    )
    if (distinctProfiles.size > 1) {
      toast.error("Нельзя запускать тест сразу для БД разных профилей модели данных")
      return false
    }

    if (testConfig.testMode === "custom_query") {
      if (!testConfig.customSql.trim()) {
        toast.error("Введите SQL-запрос")
        return false
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
        toast.info("Запуск тестирования: пользовательский SQL-запрос")
      }

      const asyncResponse = await apiClient.runAsyncTest({
        connection_ids: testConfig.databases,
        bundle_id: testConfig.testMode === "scenario" ? selectedBundle?.id : undefined,
        iterations: testConfig.iterations,
        virtual_users: testConfig.virtualUsers,
        scenario: testConfig.testMode === "scenario" ? testConfig.scenario : "custom",
        use_indexes: testConfig.testMode === "scenario" ? testConfig.useIndexes : false,
        warmup_time: testConfig.warmupTime,
        test_name: testName,
        logical_database_id: selectedLogicalDbId ?? undefined,
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
  const selectedConnections = connections.filter((connection) =>
    testConfig.databases.includes(connection.id)
  )
  const selectedProfileIds = Array.from(
    new Set(
      selectedConnections
        .map((connection) => connection.schema_profile_id)
        .filter((value): value is string => Boolean(value))
    )
  )
  const hasMissingProfiles = selectedConnections.some((connection) => !connection.schema_profile_id)
  const hasMixedProfiles = selectedProfileIds.length > 1
  const selectedBundles = selectedLogicalDatabaseDetail?.bundles || []
  const selectedProfileName =
    selectedLogicalDatabaseDetail?.schema_profile_name ||
    selectedConnections[0]?.schema_profile_name ||
    null
  const selectedBundle = selectedBundles.find(
    (bundle) => bundle.scenario_template_id === testConfig.scenario && bundle.is_active
  )

  const canRunTest = () => {
    if (testConfig.databases.length === 0) return false
    if (hasMissingProfiles || hasMixedProfiles) return false
    if (testConfig.testMode === "custom_query") {
      return testConfig.customSql.trim().length > 0
    }
    return true
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Конфигурация и запуск</h1>
        <p className="text-muted-foreground">Настройте параметры нагрузочного тестирования</p>
      </div>

      <LogicalDbSelectorCard
        databases={logicalDatabases}
        selectedId={selectedLogicalDbId}
        onSelect={handleLogicalDbSelect}
      />

      <ConnectionStatusCard connections={connections} healthStatus={healthStatus} />

      <DatabaseSelectionCard
        connections={connections}
        selectedDatabases={testConfig.databases}
        healthStatus={healthStatus}
        onToggle={handleDatabaseToggle}
      />

      {testConfig.databases.length > 0 && hasMissingProfiles && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-700">
          Для части выбранных БД ещё не подтверждён `schema_profile`. Откройте управление подключениями и назначьте профиль.
        </div>
      )}

      {testConfig.databases.length > 0 && hasMixedProfiles && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700">
          Запуск заблокирован: выбраны БД разных профилей модели данных. Оставьте только подключения одного `schema_profile`.
        </div>
      )}

      <TestModeSelectorCard
        testMode={testConfig.testMode}
        onModeChange={(mode) => setTestConfig({ testMode: mode })}
      />

      {testConfig.testMode === "scenario" && (
        <ScenarioSelectorCard
          scenarios={scenarios}
          selectedScenarioId={testConfig.scenario}
          useIndexes={testConfig.useIndexes}
          selectedProfileName={selectedProfileName}
          selectedBundleName={selectedBundle?.name || null}
          indexesCount={selectedBundle?.indexes?.length ?? 0}
          onScenarioChange={(id) => {
            setTestConfig({
              scenario: id,
              bundleId: selectedBundles.find(
                (bundle) => bundle.scenario_template_id === id && bundle.is_active
              )?.id,
              useIndexes: (
                selectedBundles.find(
                  (bundle) => bundle.scenario_template_id === id && bundle.is_active
                )?.indexes?.length ?? 0
              ) > 0 ? testConfig.useIndexes : false,
            })
          }}
          onUseIndexesChange={(value) => setTestConfig({ useIndexes: value })}
        />
      )}

      {testConfig.testMode === "custom_query" && (
        <QuerySelectorCard
          customSql={testConfig.customSql}
          onCustomSqlChange={(sql) => setTestConfig({ customSql: sql })}
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

      <ConfigSummaryCard
        selectedDatabases={testConfig.databases}
        testMode={testConfig.testMode}
        selectedScenario={selectedScenario}
        useIndexes={testConfig.useIndexes}
        virtualUsers={testConfig.virtualUsers}
        iterations={testConfig.iterations}
        warmupTime={testConfig.warmupTime}
        connections={connections}
        selectedProfileName={hasMixedProfiles ? null : selectedProfileName}
        selectedBundleName={selectedBundle?.name || null}
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
