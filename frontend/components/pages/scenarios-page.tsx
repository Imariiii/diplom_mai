"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiClient } from "@/lib/api"
import type { Scenario, ScenarioQuery, ScenarioParam, CreateScenarioRequest, CreateScenarioQueryRequest, CreateScenarioParamRequest } from "@/lib/types"
import { 
  Play, 
  Plus, 
  Copy, 
  Trash2, 
  Edit, 
  Database, 
  Code, 
  Settings,
  ChevronRight,
  ChevronDown,
  FileCode,
  Hash,
  Table,
  Check,
  X,
  AlertCircle,
  Loader2
} from "lucide-react"
import { toast } from "sonner"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"

const SCENARIO_TYPES = [
  { value: "read_only", label: "Только чтение (100% SELECT)", description: "Чистые SELECT-запросы для проверки чтения" },
  { value: "write_only", label: "Только запись (100% INSERT/UPDATE/DELETE)", description: "Тестирование производительности записи" },
  { value: "mixed_light", label: "Смешанная нагрузка лёгкая (80% SELECT, 20% UPDATE)", description: "Похоже на реальный OLTP-режим" },
  { value: "mixed_heavy", label: "Смешанная нагрузка тяжёлая (50% SELECT, 50% UPDATE)", description: "Высокая нагрузка на запись" },
  { value: "oltp", label: "OLTP-подобная нагрузка", description: "Смесь коротких транзакций" },
  { value: "olap", label: "OLAP-подобная нагрузка", description: "Сложные аналитические запросы" },
  { value: "custom", label: "Пользовательский сценарий", description: "Полностью настраиваемый" },
]

const PARAM_TYPES = [
  { value: "random_int", label: "Случайное целое число", hasMinMax: true },
  { value: "random_from_table", label: "Случайное значение из таблицы", hasTableRef: true },
  { value: "sequential_int", label: "Последовательное целое", hasMinMax: false },
  { value: "uuid", label: "UUID", hasMinMax: false },
  { value: "fixed", label: "Фиксированное значение", hasFixedValue: true },
  { value: "random_string", label: "Случайная строка", hasStringLength: true },
  { value: "random_date", label: "Случайная дата", hasMinMax: false },
]

export function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
  const [queries, setQueries] = useState<ScenarioQuery[]>([])
  const [expandedQueries, setExpandedQueries] = useState<Set<string>>(new Set())
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [editingScenario, setEditingScenario] = useState<Scenario | null>(null)

  // Create scenario form
  const [newScenarioName, setNewScenarioName] = useState("")
  const [newScenarioDescription, setNewScenarioDescription] = useState("")
  const [newScenarioType, setNewScenarioType] = useState("custom")

  // Create query form
  const [isAddQueryDialogOpen, setIsAddQueryDialogOpen] = useState(false)
  const [newQuerySql, setNewQuerySql] = useState("")
  const [newQueryType, setNewQueryType] = useState<"select" | "insert" | "update" | "delete">("select")
  const [newQueryDescription, setNewQueryDescription] = useState("")
  const [newQueryWeight, setNewQueryWeight] = useState(1)

  // Create param form
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

  useEffect(() => {
    loadScenarios()
  }, [loadScenarios])

  useEffect(() => {
    if (selectedScenario) {
      loadQueries(selectedScenario.id)
    }
  }, [selectedScenario, loadQueries])

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
      loadScenarios()
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
      loadScenarios()
      if (selectedScenario?.id === editingScenario.id) {
        const updated = await apiClient.getScenario(editingScenario.id)
        setSelectedScenario(updated)
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
      }
      loadScenarios()
    } catch (error) {
      toast.error("Не удалось удалить сценарий")
      console.error(error)
    }
  }

  const handleCloneScenario = async (scenario: Scenario) => {
    try {
      await apiClient.cloneScenario(scenario.id, `${scenario.name} (копия)`)
      toast.success("Сценарий клонирован")
      loadScenarios()
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
      loadQueries(selectedScenario.id)
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
      loadQueries(selectedScenario.id)
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
      loadQueries(selectedScenario.id)
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
      loadQueries(selectedScenario.id)
    } catch (error) {
      toast.error("Не удалось удалить параметр")
      console.error(error)
    }
  }

  const toggleQueryExpanded = (queryId: string) => {
    const newExpanded = new Set(expandedQueries)
    if (newExpanded.has(queryId)) {
      newExpanded.delete(queryId)
    } else {
      newExpanded.add(queryId)
    }
    setExpandedQueries(newExpanded)
  }

  const openEditDialog = (scenario: Scenario) => {
    setEditingScenario(scenario)
    setNewScenarioName(scenario.name)
    setNewScenarioDescription(scenario.description || "")
    setNewScenarioType(scenario.scenario_type)
    setIsEditDialogOpen(true)
  }

  const getScenarioTypeLabel = (type: string) => {
    return SCENARIO_TYPES.find(t => t.value === type)?.label || type
  }

  const getParamTypeLabel = (type: string) => {
    return PARAM_TYPES.find(t => t.value === type)?.label || type
  }

  const extractParamsFromSql = (sql: string): string[] => {
    const matches = sql.match(/\{(\w+)\}/g)
    if (!matches) return []
    return matches.map(m => m.slice(1, -1))
  }

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

      {/* Alert for built-in scenarios */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Встроенные сценарии (отмечены значком <Badge variant="secondary" className="mx-1">built-in</Badge>) 
          нельзя редактировать, но можно клонировать для создания собственной копии.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scenarios List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Доступные сценарии
            </CardTitle>
            <CardDescription>
              {scenarios.length} сценариев
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]">
              <div className="space-y-2">
                {scenarios.map((scenario) => (
                  <div
                    key={scenario.id}
                    onClick={() => setSelectedScenario(scenario)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedScenario?.id === scenario.id
                        ? "bg-primary/10 border border-primary/20"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{scenario.name}</span>
                          {scenario.is_builtin === 't' && (
                            <Badge variant="secondary" className="text-xs">built-in</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {getScenarioTypeLabel(scenario.scenario_type)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Scenario Details */}
        <Card className="lg:col-span-2">
          {selectedScenario ? (
            <>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <CardTitle>{selectedScenario.name}</CardTitle>
                      {selectedScenario.is_builtin === 't' && (
                        <Badge variant="secondary">built-in</Badge>
                      )}
                    </div>
                    <CardDescription className="mt-1">
                      {getScenarioTypeLabel(selectedScenario.scenario_type)}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => handleCloneScenario(selectedScenario)}
                      title="Клонировать"
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    {selectedScenario.is_builtin !== 't' && (
                      <>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => openEditDialog(selectedScenario)}
                          title="Редактировать"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleDeleteScenario(selectedScenario)}
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                {selectedScenario.description && (
                  <p className="text-sm text-muted-foreground mt-2">
                    {selectedScenario.description}
                  </p>
                )}
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="queries">
                  <TabsList>
                    <TabsTrigger value="queries" className="flex items-center gap-2">
                      <Code className="h-4 w-4" />
                      Запросы ({queries.length})
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="queries" className="space-y-4">
                    <div className="flex justify-end">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsAddQueryDialogOpen(true)}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Добавить запрос
                      </Button>
                    </div>

                    <ScrollArea className="h-[400px]">
                      <div className="space-y-4">
                        {queries.map((query, index) => {
                          const params = extractParamsFromSql(query.sql_template)
                          const isExpanded = expandedQueries.has(query.id)

                          return (
                            <div
                              key={query.id}
                              className="border rounded-lg overflow-hidden"
                            >
                              <div
                                className="p-4 bg-muted/50 flex items-center justify-between cursor-pointer"
                                onClick={() => toggleQueryExpanded(query.id)}
                              >
                                <div className="flex items-center gap-3">
                                  {isExpanded ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4" />
                                  )}
                                  <Badge variant={query.query_type === 'select' ? 'default' : 'secondary'}>
                                    {query.query_type.toUpperCase()}
                                  </Badge>
                                  <span className="font-medium">Запрос #{index + 1}</span>
                                  <Badge variant="outline" className="text-xs">
                                    weight: {query.weight}
                                  </Badge>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleDeleteQuery(query.id)
                                  }}
                                >
                                  <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                              </div>

                              {isExpanded && (
                                <div className="p-4 space-y-4">
                                  {query.description && (
                                    <p className="text-sm text-muted-foreground">
                                      {query.description}
                                    </p>
                                  )}

                                  <div className="bg-muted p-3 rounded-md">
                                    <pre className="text-sm overflow-x-auto">
                                      <code>{query.sql_template}</code>
                                    </pre>
                                  </div>

                                  {params.length > 0 && (
                                    <div className="space-y-2">
                                      <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-medium flex items-center gap-2">
                                          <Hash className="h-4 w-4" />
                                          Параметры ({query.params?.length || 0}/{params.length})
                                        </h4>
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => {
                                            setSelectedQueryForParam(query.id)
                                            setIsAddParamDialogOpen(true)
                                          }}
                                        >
                                          <Plus className="h-4 w-4 mr-1" />
                                          Добавить
                                        </Button>
                                      </div>

                                      {query.params && query.params.length > 0 ? (
                                        <div className="space-y-2">
                                          {query.params.map((param) => (
                                            <div
                                              key={param.id}
                                              className="flex items-center justify-between p-2 bg-muted/50 rounded"
                                            >
                                              <div className="flex items-center gap-2">
                                                <code className="text-sm bg-primary/10 px-2 py-0.5 rounded">
                                                  {param.param_name}
                                                </code>
                                                <Badge variant="outline" className="text-xs">
                                                  {getParamTypeLabel(param.param_type)}
                                                </Badge>
                                              </div>
                                              <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6"
                                                onClick={() => handleDeleteParam(query.id, param.id)}
                                              >
                                                <X className="h-3 w-3" />
                                              </Button>
                                            </div>
                                          ))}
                                        </div>
                                      ) : (
                                        <Alert variant="destructive" className="py-2">
                                          <AlertCircle className="h-4 w-4" />
                                          <AlertDescription className="text-xs">
                                            Не все параметры настроены. Нажмите "Добавить" для настройки.
                                          </AlertDescription>
                                        </Alert>
                                      )}

                                      {/* Show missing params */}
                                      {query.params && params.map(paramName => {
                                        const isConfigured = query.params!.some(p => p.param_name === paramName)
                                        if (isConfigured) return null
                                        return (
                                          <div key={paramName} className="flex items-center gap-2 text-amber-600 text-sm">
                                            <AlertCircle className="h-4 w-4" />
                                            <code className="bg-amber-100 px-1 rounded">{paramName}</code>
                                            <span>не настроен</span>
                                          </div>
                                        )
                                      })}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              </CardContent>
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

      {/* Create Scenario Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Создать сценарий</DialogTitle>
            <DialogDescription>
              Создайте новый сценарий нагрузочного тестирования
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Название</Label>
              <Input
                id="name"
                value={newScenarioName}
                onChange={(e) => setNewScenarioName(e.target.value)}
                placeholder="Например: Интенсивное чтение фильмов"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="type">Тип сценария</Label>
              <Select value={newScenarioType} onValueChange={setNewScenarioType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SCENARIO_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      <div className="flex flex-col items-start">
                        <span>{type.label}</span>
                        <span className="text-xs text-muted-foreground">
                          {type.description}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Описание (опционально)</Label>
              <Textarea
                id="description"
                value={newScenarioDescription}
                onChange={(e) => setNewScenarioDescription(e.target.value)}
                placeholder="Опишите назначение сценария..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleCreateScenario}>Создать</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Scenario Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Редактировать сценарий</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Название</Label>
              <Input
                id="edit-name"
                value={newScenarioName}
                onChange={(e) => setNewScenarioName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-type">Тип сценария</Label>
              <Select value={newScenarioType} onValueChange={setNewScenarioType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SCENARIO_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Описание</Label>
              <Textarea
                id="edit-description"
                value={newScenarioDescription}
                onChange={(e) => setNewScenarioDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleUpdateScenario}>Сохранить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Query Dialog */}
      <Dialog open={isAddQueryDialogOpen} onOpenChange={setIsAddQueryDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Добавить SQL-запрос</DialogTitle>
            <DialogDescription>
              Добавьте запрос с параметрами в формате {"{param_name}"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="query-type">Тип запроса</Label>
                <Select value={newQueryType} onValueChange={(v) => setNewQueryType(v as any)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="select">SELECT</SelectItem>
                    <SelectItem value="insert">INSERT</SelectItem>
                    <SelectItem value="update">UPDATE</SelectItem>
                    <SelectItem value="delete">DELETE</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="query-weight">Вес (приоритет)</Label>
                <Input
                  id="query-weight"
                  type="number"
                  min={1}
                  max={10}
                  value={newQueryWeight}
                  onChange={(e) => setNewQueryWeight(parseInt(e.target.value) || 1)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="query-sql">SQL шаблон</Label>
              <Textarea
                id="query-sql"
                value={newQuerySql}
                onChange={(e) => setNewQuerySql(e.target.value)}
                placeholder="SELECT * FROM film WHERE film_id = {film_id}"
                rows={4}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Используйте {"{parameter_name}"} для параметров, которые будут генерироваться автоматически
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="query-desc">Описание (опционально)</Label>
              <Input
                id="query-desc"
                value={newQueryDescription}
                onChange={(e) => setNewQueryDescription(e.target.value)}
                placeholder="Описание запроса"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddQueryDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleAddQuery}>Добавить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Param Dialog */}
      <Dialog open={isAddParamDialogOpen} onOpenChange={setIsAddParamDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Добавить параметр</DialogTitle>
            <DialogDescription>
              Настройте генерацию значений для параметра SQL-запроса
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="param-name">Имя параметра</Label>
              <Input
                id="param-name"
                value={newParamName}
                onChange={(e) => setNewParamName(e.target.value)}
                placeholder="film_id"
              />
              <p className="text-xs text-muted-foreground">
                Должно совпадать с именем в SQL шаблоне (без фигурных скобок)
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="param-type">Тип генератора</Label>
              <Select value={newParamType} onValueChange={setNewParamType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PARAM_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {newParamType === 'random_int' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Минимум</Label>
                  <Input
                    type="number"
                    value={newParamMinValue}
                    onChange={(e) => setNewParamMinValue(parseInt(e.target.value) || 0)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Максимум</Label>
                  <Input
                    type="number"
                    value={newParamMaxValue}
                    onChange={(e) => setNewParamMaxValue(parseInt(e.target.value) || 1000)}
                  />
                </div>
              </div>
            )}

            {newParamType === 'random_from_table' && (
              <>
                <div className="space-y-2">
                  <Label>Таблица</Label>
                  <Input
                    value={newParamTableRef}
                    onChange={(e) => setNewParamTableRef(e.target.value)}
                    placeholder="film"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Колонка</Label>
                  <Input
                    value={newParamColumnRef}
                    onChange={(e) => setNewParamColumnRef(e.target.value)}
                    placeholder="film_id"
                  />
                </div>
              </>
            )}

            {newParamType === 'fixed' && (
              <div className="space-y-2">
                <Label>Фиксированное значение</Label>
                <Input
                  value={newParamFixedValue}
                  onChange={(e) => setNewParamFixedValue(e.target.value)}
                  placeholder="Значение"
                />
              </div>
            )}

            {newParamType === 'random_string' && (
              <div className="space-y-2">
                <Label>Длина строки</Label>
                <Input
                  type="number"
                  value={newParamStringLength}
                  onChange={(e) => setNewParamStringLength(parseInt(e.target.value) || 10)}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddParamDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={handleAddParam}>Добавить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
