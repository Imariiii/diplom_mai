"use client"

import { useState, useEffect, useMemo } from "react"
import { Play, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { DatabaseSelectionCard, type ConnectionCheckResult } from "./config/database-selection-card"
import { TestModeSelectorCard } from "./config/test-mode-selector-card"
import { ScenarioSelectorCard } from "./config/scenario-selector-card"
import { QuerySelectorCard } from "./config/query-selector-card"
import { LoadParamsCard } from "./config/load-params-card"
import { ConfigSummaryCard } from "./config/config-summary-card"

export function ConfigPage() {
  const {
    testConfig,
    setTestConfig,
    setCurrentTest,
    setCurrentPage,
  } = useAppStore()
  const [isRunning, setIsRunning] = useState(false)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [scenarios, setScenarios] = useState<ScenarioTemplate[]>([])
  const [scenariosLoading, setScenariosLoading] = useState(true)
  const [logicalDatabases, setLogicalDatabases] = useState<LogicalDatabaseWithConnections[]>([])
  const [selectedLogicalDbId, setSelectedLogicalDbId] = useState<string | null>(null)
  const [selectedLogicalDatabaseDetail, setSelectedLogicalDatabaseDetail] = useState<LogicalDatabaseDetail | null>(null)
  const [connectionChecks, setConnectionChecks] = useState<Record<string, ConnectionCheckResult>>({})
  const [checksPending, setChecksPending] = useState(false)

  const connections: DatabaseConnection[] = useMemo(() => {
    if (!selectedLogicalDbId) return []
    return logicalDatabases.find((db) => db.id === selectedLogicalDbId)?.connections ?? []
  }, [selectedLogicalDbId, logicalDatabases])

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

  /** Проверка сохранённых подключений выбранной БД (результат — в карточке выбора СУБД) */
  useEffect(() => {
    if (connections.length === 0) {
      setConnectionChecks({})
      setChecksPending(false)
      return
    }

    let cancelled = false
    setChecksPending(true)
    setConnectionChecks({})

    void (async () => {
      const results = await Promise.all(
        connections.map(async (c) => {
          try {
            const r = await apiClient.testSavedConnection(c.id)
            const ok = Boolean(r.success)
            const message = ok
              ? (r.message?.trim() ? r.message : "Подключение успешно")
              : (r.message?.trim() || "Подключение недоступно")
            return [c.id, { ok, message }] as const
          } catch (err) {
            return [
              c.id,
              {
                ok: false,
                message: err instanceof Error ? err.message : "Ошибка проверки подключения",
              },
            ] as const
          }
        })
      )
      if (cancelled) return
      setConnectionChecks(Object.fromEntries(results) as Record<string, ConnectionCheckResult>)
      setChecksPending(false)
    })()

    return () => {
      cancelled = true
    }
  }, [connections])

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

    if (
      selectedLogicalDatabaseDetail?.profile_status === "incompatible" ||
      selectedLogicalDatabaseDetail?.compatibility_status === "invalid"
    ) {
      toast.error("Logical database несовместима: проверьте профиль и reference connection")
      return false
    }

    if (testConfig.testMode === "scenario" && !selectedBundle) {
      toast.error("Для выбранного сценария нет активного SQL bundle")
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

  const openConfirmDialog = () => {
    if (!validateConfig()) return
    setConfirmDialogOpen(true)
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
        custom_sql: testConfig.testMode === "custom_query" ? testConfig.customSql : undefined,
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
      setConfirmDialogOpen(false)
      setCurrentPage("dashboards")

      toast.success(`Тест запущен! ID: ${asyncResponse.test_id}`)
      toast.info("Подключение к real-time обновлениям...")

    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Неизвестная ошибка при запуске теста")
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
  const hasInvalidLogicalDb =
    selectedLogicalDatabaseDetail?.profile_status === "incompatible" ||
    selectedLogicalDatabaseDetail?.compatibility_status === "invalid"
  const selectedBundles = selectedLogicalDatabaseDetail?.bundles || []
  const selectedProfileName =
    selectedLogicalDatabaseDetail?.schema_profile_name ||
    selectedConnections[0]?.schema_profile_name ||
    null
  const selectedBundle = selectedBundles.find(
    (bundle) => bundle.scenario_template_id === testConfig.scenario && bundle.is_active
  )
  const hasMissingActiveBundle = testConfig.testMode === "scenario" && !selectedBundle

  const canRunTest = () => {
    if (testConfig.databases.length === 0) return false
    if (hasMissingProfiles || hasMixedProfiles) return false
    if (hasInvalidLogicalDb || hasMissingActiveBundle) return false
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

      <DatabaseSelectionCard
        connections={connections}
        selectedDatabases={testConfig.databases}
        connectionChecks={connectionChecks}
        checksPending={checksPending}
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

      {selectedLogicalDatabaseDetail && (
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <div className="font-medium">Состояние logical database</div>
          <div className="mt-1 text-muted-foreground">
            Профиль: {selectedLogicalDatabaseDetail.schema_profile_name || "не назначен"} ·
            Reference: {selectedLogicalDatabaseDetail.reference_connection_name || "не выбран"} ·
            Совместимость: {selectedLogicalDatabaseDetail.compatibility_status || "unknown"}
          </div>
          {selectedLogicalDatabaseDetail.compatibility_report?.errors?.length ? (
            <div className="mt-2 text-red-700">
              {selectedLogicalDatabaseDetail.compatibility_report.errors[0]}
            </div>
          ) : null}
        </div>
      )}

      {testConfig.databases.length > 0 && hasInvalidLogicalDb && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700">
          Запуск заблокирован: logical database помечена как несовместимая. Проверьте отчёт совместимости и эталонное подключение.
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
          activeBundle={selectedBundle ?? null}
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

      {testConfig.testMode === "scenario" && hasMissingActiveBundle && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700">
          Для выбранного logical scenario нет активного SQL bundle. Сначала сгенерируйте или активируйте bundle для профиля.
        </div>
      )}

      {testConfig.testMode === "custom_query" && (
        <QuerySelectorCard
          customSql={testConfig.customSql}
          onCustomSqlChange={(sql) => setTestConfig({ customSql: sql })}
        />
      )}

      <LoadParamsCard
        virtualUsers={testConfig.virtualUsers}
        iterations={testConfig.iterations}
        warmupTime={testConfig.warmupTime}
        onVirtualUsersChange={(v) => setTestConfig({ virtualUsers: v })}
        onIterationsChange={(v) => setTestConfig({ iterations: v })}
        onWarmupTimeChange={(v) => setTestConfig({ warmupTime: v })}
      />

      <div className="space-y-2">
        <Button
          size="lg"
          className="w-full"
          type="button"
          onClick={openConfirmDialog}
          disabled={!canRunTest() || isRunning || checksPending || scenariosLoading}
        >
          Подтвердить
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Откроется окно со сводкой параметров и кнопкой запуска нагрузочного теста
        </p>
      </div>

      <Dialog
        open={confirmDialogOpen}
        onOpenChange={(open) => {
          if (!open && isRunning) return
          setConfirmDialogOpen(open)
        }}
      >
        <DialogContent className="top-[3vh] flex w-[min(98vw,56rem)] max-w-none translate-y-0 flex-col gap-0 overflow-visible p-0 sm:max-w-none">
          <DialogHeader className="min-w-0 shrink-0 space-y-2 border-b border-border px-6 py-4 pr-14 text-left">
            <DialogTitle className="text-pretty pr-1">Сводка конфигурации</DialogTitle>
            <DialogDescription className="text-pretty break-words">
              Проверьте параметры. Запуск теста перенаправит на страницу «Дашборды».
            </DialogDescription>
          </DialogHeader>
          <div className="min-w-0 px-6 py-4">
            <ConfigSummaryCard
              embedded
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
          </div>
          <DialogFooter className="min-w-0 shrink-0 flex-col gap-2 border-t border-border px-6 py-4 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="w-full sm:w-auto"
              disabled={isRunning}
              onClick={() => setConfirmDialogOpen(false)}
            >
              Назад к настройкам
            </Button>
            <Button
              type="button"
              className="w-full sm:w-auto"
              onClick={() => void runTest()}
              disabled={!canRunTest() || isRunning}
            >
              {isRunning ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Запуск…
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Запустить тестирование
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
