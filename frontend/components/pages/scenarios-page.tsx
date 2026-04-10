"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Plus, Database, AlertCircle, Loader2 } from "lucide-react"
import { apiClient } from "@/lib/api"
import type { Scenario, ScenarioQuery, ScenarioIndex, CreateScenarioParamRequest, CreateScenarioIndexRequest } from "@/lib/types"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ScenarioListPanel } from "./scenarios/scenario-list-panel"
import { ScenarioDetailPanel } from "./scenarios/scenario-detail-panel"
import { ScenarioFormDialog } from "./scenarios/scenario-form-dialog"
import { AddQueryDialog } from "./scenarios/add-query-dialog"
import { AddParamDialog } from "./scenarios/add-param-dialog"
import { AddIndexDialog } from "./scenarios/add-index-dialog"

const SCENARIO_TYPES = [
  { value: "read_only", label: "Только чтение (100% SELECT)" },
  { value: "write_only", label: "Только запись (100% INSERT/UPDATE/DELETE)" },
  { value: "mixed_light", label: "Смешанная нагрузка лёгкая (80% SELECT, 20% UPDATE)" },
  { value: "mixed_heavy", label: "Смешанная нагрузка тяжёлая (50% SELECT, 50% UPDATE)" },
  { value: "oltp", label: "OLTP-подобная нагрузка" },
  { value: "olap", label: "OLAP-подобная нагрузка" },
  { value: "custom", label: "Пользовательский сценарий" },
]

const PARAM_TYPES = [
  { value: "random_int", label: "Случайное целое число" },
  { value: "random_from_table", label: "Случайное значение из таблицы" },
  { value: "sequential_int", label: "Последовательное целое" },
  { value: "uuid", label: "UUID" },
  { value: "fixed", label: "Фиксированное значение" },
  { value: "random_string", label: "Случайная строка" },
  { value: "random_date", label: "Случайная дата" },
]

export function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
  const [queries, setQueries] = useState<ScenarioQuery[]>([])
  const [indexes, setIndexes] = useState<ScenarioIndex[]>([])
  const [expandedQueries, setExpandedQueries] = useState<Set<string>>(new Set())

  // Dialog state
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [editingScenario, setEditingScenario] = useState<Scenario | null>(null)

  // Create/Edit scenario form
  const [newScenarioName, setNewScenarioName] = useState("")
  const [newScenarioDescription, setNewScenarioDescription] = useState("")
  const [newScenarioType, setNewScenarioType] = useState("custom")

  // Add query form
  const [isAddQueryDialogOpen, setIsAddQueryDialogOpen] = useState(false)
  const [newQuerySql, setNewQuerySql] = useState("")
  const [newQueryType, setNewQueryType] = useState<"select" | "insert" | "update" | "delete">("select")
  const [newQueryDescription, setNewQueryDescription] = useState("")
  const [newQueryWeight, setNewQueryWeight] = useState(1)

  // Add param form
  const [isAddParamDialogOpen, setIsAddParamDialogOpen] = useState(false)
  const [selectedQueryForParam, setSelectedQueryForParam] = useState<string | null>(null)
  const [newParamName, setNewParamName] = useState("")
  const [newParamType, setNewParamType] = useState("random_int")
  const [newParamMinValue, setNewParamMinValue] = useState(1)
  const [newParamMaxValue, setNewParamMaxValue] = useState(1000)
  const [newParamTableRef, setNewParamTableRef] = useState("")
  const [newParamColumnRef, setNewParamColumnRef] = useState("")
  const [newParamFixedValue, setNewParamFixedValue] = useState("")
  const [newParamStringLength, setNewParamStringLength] = useState(10)

  // Add index form
  const [isAddIndexDialogOpen, setIsAddIndexDialogOpen] = useState(false)
  const [newIndexTableName, setNewIndexTableName] = useState("")
  const [newIndexColumnNames, setNewIndexColumnNames] = useState("")
  const [newIndexType, setNewIndexType] = useState("btree")
  const [newIndexName, setNewIndexName] = useState("")
  const [newIndexDescription, setNewIndexDescription] = useState("")
  const [newIndexCondition, setNewIndexCondition] = useState("")
  const [newIndexIsUnique, setNewIndexIsUnique] = useState(false)

  const loadScenarios = useCallback(async () => {
    try {
      setLoading(true)
      const response = await apiClient.getScenarios()
      setScenarios(response.scenarios)
    } catch (error) {
      toast.error("Не удалось загрузить сценарии")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadQueries = useCallback(async (scenarioId: string) => {
    try {
      const response = await apiClient.getScenarioQueries(scenarioId)
      setQueries(response.queries)
    } catch (error) {
      toast.error("Не удалось загрузить запросы сценария")
      console.error(error)
    }
  }, [])

  const loadIndexes = useCallback(async (scenarioId: string) => {
    try {
      const response = await apiClient.getScenarioIndexes(scenarioId)
      setIndexes(response.indexes)
    } catch (error) {
      toast.error("Не удалось загрузить индексы сценария")
      console.error(error)
    }
  }, [])

  const refreshSelectedScenario = useCallback(async (scenarioId: string) => {
    try {
      const fullScenario = await apiClient.getScenario(scenarioId)
      setSelectedScenario(fullScenario)
      setQueries(fullScenario.queries || [])
      setIndexes(fullScenario.indexes || [])
    } catch (error) {
      toast.error("Не удалось загрузить детали сценария")
      console.error(error)
    }
  }, [])

  useEffect(() => {
    loadScenarios()
  }, [loadScenarios])

  useEffect(() => {
    if (selectedScenario?.id) {
      refreshSelectedScenario(selectedScenario.id)
    }
  }, [selectedScenario?.id, refreshSelectedScenario])

  // ==================== CRUD Handlers ====================

  const handleCreateScenario = async () => {
    if (!newScenarioName.trim()) {
      toast.error("Введите название сценария")
      return
    }
    try {
      await apiClient.createScenario({
        name: newScenarioName,
        description: newScenarioDescription,
        scenario_type: newScenarioType,
      })
      toast.success("Сценарий создан")
      setIsCreateDialogOpen(false)
      setNewScenarioName("")
      setNewScenarioDescription("")
      setNewScenarioType("custom")
      await loadScenarios()
    } catch (error) {
      toast.error("Не удалось создать сценарий")
      console.error(error)
    }
  }

  const handleUpdateScenario = async () => {
    if (!editingScenario) return
    if (!newScenarioName.trim()) {
      toast.error("Введите название сценария")
      return
    }
    try {
      await apiClient.updateScenario(editingScenario.id, {
        name: newScenarioName,
        description: newScenarioDescription,
        scenario_type: newScenarioType,
      })
      toast.success("Сценарий обновлён")
      setIsEditDialogOpen(false)
      setEditingScenario(null)
      await loadScenarios()
      if (selectedScenario?.id === editingScenario.id) {
        await refreshSelectedScenario(editingScenario.id)
      }
    } catch (error) {
      toast.error("Не удалось обновить сценарий")
      console.error(error)
    }
  }

  const handleDeleteScenario = async (scenario: Scenario) => {
    if (scenario.is_builtin === 't') {
      toast.error("Встроенные сценарии нельзя удалить")
      return
    }
    if (!confirm(`Удалить сценарий "${scenario.name}"?`)) return
    try {
      await apiClient.deleteScenario(scenario.id)
      toast.success("Сценарий удалён")
      if (selectedScenario?.id === scenario.id) {
        setSelectedScenario(null)
        setQueries([])
        setIndexes([])
      }
      await loadScenarios()
    } catch (error) {
      toast.error("Не удалось удалить сценарий")
      console.error(error)
    }
  }

  const handleCloneScenario = async (scenario: Scenario) => {
    try {
      await apiClient.cloneScenario(scenario.id, `${scenario.name} (копия)`)
      toast.success("Сценарий клонирован")
      await loadScenarios()
    } catch (error) {
      toast.error("Не удалось клонировать сценарий")
      console.error(error)
    }
  }

  const handleAddQuery = async () => {
    if (!selectedScenario) return
    if (!newQuerySql.trim()) {
      toast.error("Введите SQL-запрос")
      return
    }
    try {
      await apiClient.createScenarioQuery(selectedScenario.id, {
        sql_template: newQuerySql,
        query_type: newQueryType,
        description: newQueryDescription,
        weight: newQueryWeight,
      })
      toast.success("Запрос добавлен")
      setIsAddQueryDialogOpen(false)
      setNewQuerySql("")
      setNewQueryDescription("")
      setNewQueryWeight(1)
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось добавить запрос")
      console.error(error)
    }
  }

  const handleDeleteQuery = async (queryId: string) => {
    if (!selectedScenario) return
    if (!confirm("Удалить этот запрос?")) return
    try {
      await apiClient.deleteScenarioQuery(selectedScenario.id, queryId)
      toast.success("Запрос удалён")
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось удалить запрос")
      console.error(error)
    }
  }

  const handleAddParam = async () => {
    if (!selectedScenario || !selectedQueryForParam) return
    if (!newParamName.trim()) {
      toast.error("Введите имя параметра")
      return
    }
    const paramData: CreateScenarioParamRequest = {
      param_name: newParamName,
      param_type: newParamType as any,
    }
    if (newParamType === 'random_int') {
      paramData.min_value = newParamMinValue
      paramData.max_value = newParamMaxValue
    } else if (newParamType === 'random_from_table') {
      paramData.table_ref = newParamTableRef
      paramData.column_ref = newParamColumnRef
    } else if (newParamType === 'fixed') {
      paramData.fixed_value = newParamFixedValue
    } else if (newParamType === 'random_string') {
      paramData.string_length = newParamStringLength
    }
    try {
      await apiClient.createScenarioParam(selectedScenario.id, selectedQueryForParam, paramData)
      toast.success("Параметр добавлен")
      setIsAddParamDialogOpen(false)
      setNewParamName("")
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось добавить параметр")
      console.error(error)
    }
  }

  const handleDeleteParam = async (queryId: string, paramId: string) => {
    if (!selectedScenario) return
    if (!confirm("Удалить этот параметр?")) return
    try {
      await apiClient.deleteScenarioParam(selectedScenario.id, queryId, paramId)
      toast.success("Параметр удалён")
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось удалить параметр")
      console.error(error)
    }
  }

  const handleAddIndex = async () => {
    if (!selectedScenario) return
    if (!newIndexTableName.trim() || !newIndexColumnNames.trim()) {
      toast.error("Укажите таблицу и список колонок")
      return
    }

    const payload: CreateScenarioIndexRequest = {
      table_name: newIndexTableName.trim(),
      column_names: newIndexColumnNames.trim(),
      index_type: newIndexType,
      is_unique: newIndexIsUnique,
      description: newIndexDescription.trim() || undefined,
      condition: newIndexCondition.trim() || undefined,
      index_name: newIndexName.trim() || undefined,
    }

    try {
      await apiClient.createScenarioIndex(selectedScenario.id, payload)
      toast.success("Индекс добавлен")
      setIsAddIndexDialogOpen(false)
      setNewIndexTableName("")
      setNewIndexColumnNames("")
      setNewIndexType("btree")
      setNewIndexName("")
      setNewIndexDescription("")
      setNewIndexCondition("")
      setNewIndexIsUnique(false)
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось добавить индекс")
      console.error(error)
    }
  }

  const handleDeleteIndex = async (indexId: string) => {
    if (!selectedScenario) return
    if (!confirm("Удалить этот индекс?")) return

    try {
      await apiClient.deleteScenarioIndex(selectedScenario.id, indexId)
      toast.success("Индекс удалён")
      await refreshSelectedScenario(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось удалить индекс")
      console.error(error)
    }
  }

  // ==================== Helpers ====================

  const toggleQueryExpanded = (queryId: string) => {
    const newExpanded = new Set(expandedQueries)
    if (newExpanded.has(queryId)) newExpanded.delete(queryId)
    else newExpanded.add(queryId)
    setExpandedQueries(newExpanded)
  }

  const openEditDialog = (scenario: Scenario) => {
    setEditingScenario(scenario)
    setNewScenarioName(scenario.name)
    setNewScenarioDescription(scenario.description || "")
    setNewScenarioType(scenario.scenario_type)
    setIsEditDialogOpen(true)
  }

  const getScenarioTypeLabel = (type: string) =>
    SCENARIO_TYPES.find(t => t.value === type)?.label || type

  const getParamTypeLabel = (type: string) =>
    PARAM_TYPES.find(t => t.value === type)?.label || type

  const extractParamsFromSql = (sql: string): string[] => {
    const matches = sql.match(/\{(\w+)\}/g)
    if (!matches) return []
    return matches.map(m => m.slice(1, -1))
  }

  // ==================== Render ====================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Сценарии тестирования</h1>
          <p className="text-muted-foreground">
            Управление сценариями нагрузочного тестирования с параметризованными SQL-запросами
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Создать сценарий
        </Button>
      </div>

      {/* Alert */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Встроенные сценарии (отмечены значком <Badge variant="secondary" className="mx-1">built-in</Badge>)
          нельзя редактировать, но можно клонировать для создания собственной копии.
        </AlertDescription>
      </Alert>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scenarios List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Доступные сценарии
            </CardTitle>
            <CardDescription>{scenarios.length} сценариев</CardDescription>
          </CardHeader>
          <CardContent>
            <ScenarioListPanel
              scenarios={scenarios}
              selectedScenario={selectedScenario}
              onSelect={setSelectedScenario}
            />
          </CardContent>
        </Card>

        {/* Scenario Details */}
        <Card className="lg:col-span-2">
          {selectedScenario ? (
            <>
              <CardHeader className="pb-4">
                <ScenarioDetailPanel
                  selectedScenario={selectedScenario}
                  queries={queries}
                  indexes={indexes}
                  expandedQueries={expandedQueries}
                  onClone={() => handleCloneScenario(selectedScenario)}
                  onEdit={() => openEditDialog(selectedScenario)}
                  onDelete={() => handleDeleteScenario(selectedScenario)}
                  onAddQuery={() => setIsAddQueryDialogOpen(true)}
                  onAddIndex={() => setIsAddIndexDialogOpen(true)}
                  onDeleteQuery={handleDeleteQuery}
                  onDeleteIndex={handleDeleteIndex}
                  onToggleQuery={toggleQueryExpanded}
                  onAddParam={(queryId) => {
                    setSelectedQueryForParam(queryId)
                    setIsAddParamDialogOpen(true)
                  }}
                  onDeleteParam={handleDeleteParam}
                  extractParamsFromSql={extractParamsFromSql}
                />
              </CardHeader>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-[500px] text-center p-8">
              <Database className="h-16 w-16 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium text-muted-foreground">
                Выберите сценарий для просмотра
              </h3>
              <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                Сценарии содержат набор SQL-запросов с параметрами для нагрузочного тестирования
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Dialogs */}
      <ScenarioFormDialog
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
        mode="create"
        name={newScenarioName}
        onNameChange={setNewScenarioName}
        description={newScenarioDescription}
        onDescriptionChange={setNewScenarioDescription}
        scenarioType={newScenarioType}
        onScenarioTypeChange={setNewScenarioType}
        onSubmit={handleCreateScenario}
      />

      <ScenarioFormDialog
        open={isEditDialogOpen}
        onOpenChange={setIsEditDialogOpen}
        mode="edit"
        name={newScenarioName}
        onNameChange={setNewScenarioName}
        description={newScenarioDescription}
        onDescriptionChange={setNewScenarioDescription}
        scenarioType={newScenarioType}
        onScenarioTypeChange={setNewScenarioType}
        onSubmit={handleUpdateScenario}
      />

      <AddQueryDialog
        open={isAddQueryDialogOpen}
        onOpenChange={setIsAddQueryDialogOpen}
        queryType={newQueryType}
        onQueryTypeChange={setNewQueryType}
        weight={newQueryWeight}
        onWeightChange={setNewQueryWeight}
        sql={newQuerySql}
        onSqlChange={setNewQuerySql}
        description={newQueryDescription}
        onDescriptionChange={setNewQueryDescription}
        onSubmit={handleAddQuery}
      />

      <AddParamDialog
        open={isAddParamDialogOpen}
        onOpenChange={setIsAddParamDialogOpen}
        paramName={newParamName}
        onParamNameChange={setNewParamName}
        paramType={newParamType}
        onParamTypeChange={setNewParamType}
        minValue={newParamMinValue}
        onMinValueChange={setNewParamMinValue}
        maxValue={newParamMaxValue}
        onMaxValueChange={setNewParamMaxValue}
        tableRef={newParamTableRef}
        onTableRefChange={setNewParamTableRef}
        columnRef={newParamColumnRef}
        onColumnRefChange={setNewParamColumnRef}
        fixedValue={newParamFixedValue}
        onFixedValueChange={setNewParamFixedValue}
        stringLength={newParamStringLength}
        onStringLengthChange={setNewParamStringLength}
        onSubmit={handleAddParam}
      />

      <AddIndexDialog
        open={isAddIndexDialogOpen}
        onOpenChange={setIsAddIndexDialogOpen}
        tableName={newIndexTableName}
        onTableNameChange={setNewIndexTableName}
        columnNames={newIndexColumnNames}
        onColumnNamesChange={setNewIndexColumnNames}
        indexType={newIndexType}
        onIndexTypeChange={setNewIndexType}
        indexName={newIndexName}
        onIndexNameChange={setNewIndexName}
        description={newIndexDescription}
        onDescriptionChange={setNewIndexDescription}
        condition={newIndexCondition}
        onConditionChange={setNewIndexCondition}
        isUnique={newIndexIsUnique}
        onIsUniqueChange={setNewIndexIsUnique}
        onSubmit={handleAddIndex}
      />
    </div>
  )
}
