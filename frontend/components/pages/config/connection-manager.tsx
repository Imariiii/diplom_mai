"use client"

import { useState, useEffect } from "react"
import { Plus, Pencil, Trash2, Play, CheckCircle, XCircle, Loader2, Database, FolderOpen } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { apiClient } from "@/lib/api"
import type {
  ConnectionProfileAssignRequest,
  ConnectionCreateRequest,
  ConnectionSchemaPreview,
  ConnectionTestResponse,
  DatabaseConnection,
  SchemaProfileSummary,
  SupportedDbmsType,
} from "@/lib/types"
import { toast } from "sonner"

interface ConnectionManagerProps {
  onConnectionsChange?: (connections: DatabaseConnection[]) => void
}

const DBMS_OPTIONS = [
  { value: "mysql", label: "MySQL" },
  { value: "mariadb", label: "MariaDB" },
  { value: "postgresql", label: "PostgreSQL" },
]

const DEFAULT_PORTS: Record<SupportedDbmsType, number> = {
  mysql: 3306,
  mariadb: 3306,
  postgresql: 5432,
}

const DBMS_STYLES: Record<SupportedDbmsType, { color: string; icon: string }> = {
  mysql: {
    color: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    icon: "🐬",
  },
  mariadb: {
    color: "bg-violet-500/10 text-violet-500 border-violet-500/20",
    icon: "🦭",
  },
  postgresql: {
    color: "bg-indigo-500/10 text-indigo-500 border-indigo-500/20",
    icon: "🐘",
  },
}

const DEFAULT_GROUPS = ["local", "staging", "production"]
const GENERATABLE_SCENARIO_TYPES = [
  { value: "read_only", label: "Только чтение" },
  { value: "write_only", label: "Только запись" },
  { value: "mixed_light", label: "Смешанная лёгкая" },
  { value: "mixed_heavy", label: "Смешанная тяжёлая" },
  { value: "oltp", label: "OLTP" },
  { value: "olap", label: "OLAP" },
]
const TEMPLATE_LABELS: Record<string, string> = {
  select_by_pk: "SELECT по PK",
  select_projection_by_pk: "SELECT набора колонок",
  select_by_fk: "SELECT по FK",
  select_join_fk: "JOIN по FK",
  select_join_chain: "JOIN-цепочка",
  aggregation_count_group: "COUNT + GROUP BY",
  aggregation_sum_numeric: "SUM/AVG",
  range_scan_date: "Range scan по дате",
  range_scan_numeric: "Range scan по числу",
  update_timestamp_by_pk: "UPDATE timestamp",
  update_numeric_by_pk: "UPDATE numeric",
  insert_basic: "INSERT",
  delete_by_pk: "DELETE по PK",
}
const CAPABILITY_LABELS: Record<string, string> = {
  readable: "PK lookup",
  joinable: "JOIN",
  aggregatable: "aggregation",
  range_scannable: "range scan",
  updatable: "update",
  insert_safe: "insert",
  delete_safe: "delete",
}

export function ConnectionManager({ onConnectionsChange }: ConnectionManagerProps) {
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [groups, setGroups] = useState<string[]>([])
  const [selectedGroup, setSelectedGroup] = useState<string>("all")
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingConnection, setEditingConnection] = useState<DatabaseConnection | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)

  const [formData, setFormData] = useState<ConnectionCreateRequest>({
    name: "",
    dbms_type: "mysql",
    host: "localhost",
    port: 3306,
    user: "",
    password: "",
    database: "",
    group: "local",
  })
  const [testingForm, setTestingForm] = useState<ConnectionTestResponse | null>(null)
  const [testingFormLoading, setTestingFormLoading] = useState(false)
  const [schemaDialogOpen, setSchemaDialogOpen] = useState(false)
  const [schemaPreviewConnection, setSchemaPreviewConnection] = useState<DatabaseConnection | null>(null)
  const [schemaPreview, setSchemaPreview] = useState<ConnectionSchemaPreview | null>(null)
  const [availableProfiles, setAvailableProfiles] = useState<SchemaProfileSummary[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)
  const [generatingScenarios, setGeneratingScenarios] = useState(false)
  const [selectedScenarioTypes, setSelectedScenarioTypes] = useState<string[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [customProfileName, setCustomProfileName] = useState("")
  const [customProfileDescription, setCustomProfileDescription] = useState("")

  useEffect(() => {
    loadConnections()
  }, [selectedGroup])

  const loadConnections = async () => {
    setLoading(true)
    try {
      const groupParam = selectedGroup === "all" ? undefined : selectedGroup
      const data = await apiClient.getConnections(groupParam)
      setConnections(data.connections)
      setGroups(data.groups)
      onConnectionsChange?.(data.connections)
    } catch (error) {
      console.error("Ошибка загрузки подключений:", error)
      toast.error("Не удалось загрузить подключения")
    } finally {
      setLoading(false)
    }
  }

  const openCreateDialog = () => {
    setEditingConnection(null)
    setFormData({
      name: "",
      dbms_type: "mysql",
      host: "localhost",
      port: 3306,
      user: "",
      password: "",
      database: "",
      group: "local",
    })
    setTestingForm(null)
    setDialogOpen(true)
  }

  const openEditDialog = (conn: DatabaseConnection) => {
    setEditingConnection(conn)
    setFormData({
      name: conn.name,
      dbms_type: conn.dbms_type,
      host: conn.host,
      port: conn.port,
      user: conn.user,
      password: "",
      database: conn.database,
      group: conn.group || "local",
    })
    setTestingForm(null)
    setDialogOpen(true)
  }

  const handleDbmsTypeChange = (dbmsType: string) => {
    const typedDbmsType = dbmsType as SupportedDbmsType
    setFormData({
      ...formData,
      dbms_type: typedDbmsType,
      port: DEFAULT_PORTS[typedDbmsType],
    })
  }

  const testFormConnection = async () => {
    setTestingFormLoading(true)
    try {
      const result = await apiClient.testConnection({
        host: formData.host,
        port: formData.port,
        user: formData.user,
        password: formData.password,
        database: formData.database,
        dbms_type: formData.dbms_type,
      })
      setTestingForm(result)
      if (result.success) {
        toast.success(result.message)
      } else {
        toast.error(result.message)
      }
    } catch (error) {
      setTestingForm({ success: false, message: error instanceof Error ? error.message : "Ошибка тестирования", response_time_ms: null })
      toast.error("Ошибка тестирования подключения")
    } finally {
      setTestingFormLoading(false)
    }
  }

  const saveConnection = async () => {
    if (!formData.name.trim()) {
      toast.error("Введите имя подключения")
      return
    }
    if (!formData.password && !editingConnection) {
      toast.error("Введите пароль")
      return
    }

    try {
      if (editingConnection) {
        const updateData: Record<string, unknown> = {
          name: formData.name,
          host: formData.host,
          port: formData.port,
          user: formData.user,
          database: formData.database,
          group: formData.group,
        }
        if (formData.password) {
          updateData.password = formData.password
        }
        await apiClient.updateConnection(editingConnection.id, updateData)
        toast.success("Подключение обновлено")
      } else {
        await apiClient.createConnection(formData)
        toast.success("Подключение создано")
      }
      setDialogOpen(false)
      loadConnections()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка сохранения")
    }
  }

  const deleteConnection = async (id: string) => {
    if (!confirm("Удалить это подключение?")) return
    try {
      await apiClient.deleteConnection(id)
      toast.success("Подключение удалено")
      loadConnections()
    } catch (error) {
      toast.error("Ошибка удаления подключения")
    }
  }

  const testConnection = async (id: string) => {
    setTestingId(id)
    try {
      const result = await apiClient.testSavedConnection(id)
      if (result.success) {
        toast.success(`${result.message} (${result.response_time_ms?.toFixed(0)} мс)`)
      } else {
        toast.error(result.message)
      }
    } catch (error) {
      toast.error("Ошибка тестирования подключения")
    } finally {
      setTestingId(null)
    }
  }

  const openScenarioGenerationDialog = async (connection: DatabaseConnection) => {
    setSchemaDialogOpen(true)
    setSchemaPreviewConnection(connection)
    setSchemaPreview(null)
    setAvailableProfiles([])
    setSelectedScenarioTypes([])
    setSelectedProfileId(connection.schema_profile_id || "")
    setCustomProfileName(connection.detected_profile_name || "")
    setCustomProfileDescription("")
    setSchemaLoading(true)
    try {
      const [preview, profilesResponse] = await Promise.all([
        apiClient.getConnectionSchema(connection.id),
        apiClient.getSchemaProfiles(),
      ])
      setSchemaPreview(preview)
      setAvailableProfiles(profilesResponse.profiles)
      setSelectedScenarioTypes(preview.available_scenario_types)
      setSelectedProfileId(
        connection.schema_profile_id ||
        preview.current_profile?.id ||
        preview.suggested_profile?.existing_profile_id ||
        ""
      )
      setCustomProfileName(
        preview.suggested_profile?.name ||
        connection.detected_profile_name ||
        ""
      )
      setCustomProfileDescription(preview.suggested_profile?.description || "")
      if (preview.total_tables === 0) {
        toast.error("В схеме не найдено пользовательских таблиц")
      }
    } catch (error) {
      console.error("Ошибка загрузки схемы:", error)
      toast.error("Не удалось проанализировать схему БД")
    } finally {
      setSchemaLoading(false)
    }
  }

  const toggleScenarioType = (scenarioType: string, checked: boolean) => {
    setSelectedScenarioTypes((current) => {
      if (checked) {
        return current.includes(scenarioType) ? current : [...current, scenarioType]
      }
      return current.filter((item) => item !== scenarioType)
    })
  }

  const assignProfile = async (): Promise<DatabaseConnection | null> => {
    if (!schemaPreviewConnection) {
      return null
    }

    const payload: ConnectionProfileAssignRequest = {
      profile_source: "manual",
      reference_connection_id: schemaPreviewConnection.id,
    }

    if (selectedProfileId) {
      payload.schema_profile_id = selectedProfileId
    } else if (customProfileName.trim()) {
      payload.profile_name = customProfileName.trim()
      payload.description = customProfileDescription.trim() || undefined
    } else {
      toast.error("Выберите существующий профиль или укажите имя нового")
      return null
    }

    const updated = await apiClient.assignConnectionProfile(schemaPreviewConnection.id, payload)
    await loadConnections()
    setSchemaPreviewConnection(updated)
    setSelectedProfileId(updated.schema_profile_id || payload.schema_profile_id || "")
    toast.success(`Профиль '${updated.schema_profile_name || payload.profile_name}' назначен`)
    return updated
  }

  const generateScenarios = async () => {
    if (!schemaPreviewConnection) {
      return
    }
    if (selectedScenarioTypes.length === 0) {
      toast.error("Выберите хотя бы один тип сценария")
      return
    }

    setGeneratingScenarios(true)
    try {
      const updatedConnection = await assignProfile()
      const profileId = updatedConnection?.schema_profile_id
      if (!profileId) {
        throw new Error("Не удалось определить profile_id для генерации bundle'ов")
      }

      const result = await apiClient.generateProfileBundles(profileId, {
        reference_connection_id: schemaPreviewConnection.id,
        scenario_template_ids: selectedScenarioTypes,
      })
      toast.success(`Сгенерировано bundle'ов: ${result.generated_count}`)
      setSchemaDialogOpen(false)
    } catch (error) {
      console.error("Ошибка генерации bundle'ов:", error)
      toast.error(error instanceof Error ? error.message : "Не удалось сгенерировать bundle'ы")
    } finally {
      setGeneratingScenarios(false)
    }
  }

  const getDbmsColor = (dbmsType: string) => {
    return DBMS_STYLES[dbmsType as SupportedDbmsType]?.color || DBMS_STYLES.mysql.color
  }

  const getDbmsIcon = (dbmsType: string) => {
    return DBMS_STYLES[dbmsType as SupportedDbmsType]?.icon || DBMS_STYLES.mysql.icon
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Подключения к базам данных
            </CardTitle>
            <CardDescription>Управление подключениями к тестируемым СУБД</CardDescription>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                Добавить
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>
                  {editingConnection ? "Редактировать подключение" : "Новое подключение"}
                </DialogTitle>
                <DialogDescription>
                  {editingConnection
                    ? "Измените параметры подключения к базе данных"
                    : "Добавьте новое подключение к базе данных для нагрузочного тестирования"}
                </DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Имя подключения</Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Например: Sakila Local"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dbms_type">Тип СУБД</Label>
                    <Select value={formData.dbms_type} onValueChange={handleDbmsTypeChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DBMS_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="host">Хост</Label>
                    <Input
                      id="host"
                      value={formData.host}
                      onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                      placeholder="localhost"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="port">Порт</Label>
                    <Input
                      id="port"
                      type="number"
                      value={formData.port}
                      onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="user">Пользователь</Label>
                    <Input
                      id="user"
                      value={formData.user}
                      onChange={(e) => setFormData({ ...formData, user: e.target.value })}
                      placeholder="root"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">Пароль</Label>
                    <Input
                      id="password"
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      placeholder={editingConnection ? "Оставьте пустым, если не меняете" : "••••••"}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="database">Имя базы данных</Label>
                    <Input
                      id="database"
                      value={formData.database}
                      onChange={(e) => setFormData({ ...formData, database: e.target.value })}
                      placeholder="sakila"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="group">Группа</Label>
                    <Select
                      value={formData.group}
                      onValueChange={(v) => setFormData({ ...formData, group: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[...new Set([...DEFAULT_GROUPS, ...groups])].map((g) => (
                          <SelectItem key={g} value={g}>
                            {g}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {testingForm && (
                  <div className={`p-3 rounded-lg border ${
                    testingForm.success
                      ? "bg-green-500/10 border-green-500/20 text-green-600"
                      : "bg-red-500/10 border-red-500/20 text-red-600"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testingForm.success ? (
                        <CheckCircle className="h-4 w-4" />
                      ) : (
                        <XCircle className="h-4 w-4" />
                      )}
                      <span className="text-sm">{testingForm.message}</span>
                      {testingForm.response_time_ms && (
                        <span className="text-xs ml-auto">{testingForm.response_time_ms.toFixed(0)} мс</span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <DialogFooter className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={testFormConnection}
                  disabled={testingFormLoading}
                >
                  {testingFormLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Тестировать
                </Button>
                <Button onClick={saveConnection}>
                  {editingConnection ? "Сохранить" : "Создать"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Dialog open={schemaDialogOpen} onOpenChange={setSchemaDialogOpen}>
            <DialogContent className="max-h-[90vh] w-[95vw] max-w-5xl overflow-hidden p-0">
              <DialogHeader className="px-6 pt-6">
                <DialogTitle>
                  Профиль схемы и bundle'ы для {schemaPreviewConnection?.name || "подключения"}
                </DialogTitle>
                <DialogDescription>
                  Подтвердите или переопределите schema profile, затем сгенерируйте канонические SQL bundle'ы
                </DialogDescription>
              </DialogHeader>

              <ScrollArea className="h-[calc(90vh-170px)] px-6">
                <div className="space-y-4 pb-6">
                  {schemaLoading ? (
                    <div className="flex items-center justify-center py-12 text-muted-foreground">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Анализ схемы...
                    </div>
                  ) : schemaPreview ? (
                    <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg border p-3">
                      <div className="text-sm text-muted-foreground">Таблицы</div>
                      <div className="text-2xl font-semibold">{schemaPreview.total_tables}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-sm text-muted-foreground">СУБД</div>
                      <div className="text-2xl font-semibold">{schemaPreview.dbms_type}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-sm text-muted-foreground">Доступные типы</div>
                      <div className="text-2xl font-semibold">{schemaPreview.available_scenario_types.length}</div>
                    </div>
                  </div>

                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg bg-muted/50 p-3">
                        <div className="text-sm text-muted-foreground">Текущий профиль</div>
                        <div className="font-medium">
                          {schemaPreview.current_profile?.name || schemaPreviewConnection?.schema_profile_name || "не назначен"}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {schemaPreview.current_profile?.description || "Пока профиль не подтверждён вручную"}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/50 p-3">
                        <div className="text-sm text-muted-foreground">Автопредложение</div>
                        <div className="font-medium">
                          {schemaPreview.suggested_profile?.name || "не найдено"}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {schemaPreview.suggested_profile
                            ? `${Math.round(schemaPreview.suggested_profile.confidence * 100)}% · ${schemaPreview.suggested_profile.reason}`
                            : "Автоопределение не дало результата"}
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Назначить существующий профиль</Label>
                        <Select value={selectedProfileId || "custom"} onValueChange={(value) => setSelectedProfileId(value === "custom" ? "" : value)}>
                          <SelectTrigger>
                            <SelectValue placeholder="Выберите профиль или создайте новый" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="custom">Создать / использовать suggested</SelectItem>
                            {availableProfiles.map((profile) => (
                              <SelectItem key={profile.id} value={profile.id}>
                                {profile.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {!selectedProfileId && (
                        <div className="space-y-2">
                          <Label>Имя нового профиля</Label>
                          <Input
                            value={customProfileName}
                            onChange={(e) => setCustomProfileName(e.target.value)}
                            placeholder="Например: olist_like"
                          />
                        </div>
                      )}
                    </div>

                    {!selectedProfileId && (
                      <div className="space-y-2">
                        <Label>Описание профиля</Label>
                        <Input
                          value={customProfileDescription}
                          onChange={(e) => setCustomProfileDescription(e.target.value)}
                          placeholder="Краткое описание модели данных"
                        />
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Logical scenario templates для генерации bundle'ов</Label>
                    <div className="grid gap-2 md:grid-cols-2">
                      {GENERATABLE_SCENARIO_TYPES.map((scenarioType) => {
                        const available = schemaPreview.available_scenario_types.includes(scenarioType.value)
                        const checked = selectedScenarioTypes.includes(scenarioType.value)
                        return (
                          <label
                            key={scenarioType.value}
                            className={`flex items-start gap-3 rounded-lg border p-3 ${
                              available ? "cursor-pointer" : "opacity-50"
                            }`}
                          >
                            <Checkbox
                              checked={checked}
                              disabled={!available || generatingScenarios}
                              onCheckedChange={(value) => toggleScenarioType(scenarioType.value, value === true)}
                            />
                            <div className="space-y-1">
                              <div className="text-sm font-medium">{scenarioType.label}</div>
                              {!available && (
                                <div className="text-xs text-muted-foreground">
                                  Для текущей схемы не нашлось подходящих шаблонов
                                </div>
                              )}
                            </div>
                          </label>
                        )
                      })}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Таблицы и подходящие шаблоны</Label>
                    <ScrollArea className="h-72 rounded-lg border p-3">
                      <div className="space-y-3">
                        {schemaPreview.tables.map((table) => (
                          <div key={table.name} className="rounded-lg border p-3">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <div className="font-medium break-all">
                                  <code>{table.name}</code>
                                </div>
                                <div className="text-xs text-muted-foreground mt-1">
                                  строк: {table.row_count} | PK: {table.primary_key.join(", ") || "нет"}
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {table.capabilities.map((capability) => (
                                  <Badge key={capability} variant="outline" className="text-xs">
                                    {CAPABILITY_LABELS[capability] || capability}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                            <div className="text-xs text-muted-foreground mt-3">
                              Шаблоны: {schemaPreview.matching_templates[table.name]?.length
                                ? schemaPreview.matching_templates[table.name]
                                    .map((templateId) => TEMPLATE_LABELS[templateId] || templateId)
                                    .join(", ")
                                : "нет подходящих"}
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                    </div>
                  ) : (
                    <div className="py-8 text-sm text-muted-foreground">
                      Не удалось загрузить превью схемы.
                    </div>
                  )}
                </div>
              </ScrollArea>

              <DialogFooter className="border-t px-6 py-4">
                <Button
                  variant="outline"
                  onClick={() => setSchemaDialogOpen(false)}
                  disabled={generatingScenarios}
                >
                  Отмена
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    void assignProfile()
                  }}
                  disabled={schemaLoading || generatingScenarios || !schemaPreview}
                >
                  Подтвердить профиль
                </Button>
                <Button
                  onClick={generateScenarios}
                  disabled={schemaLoading || generatingScenarios || !schemaPreview}
                >
                  {generatingScenarios ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Database className="mr-2 h-4 w-4" />
                  )}
                  Сгенерировать bundle'ы
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>

      <CardContent>
        {groups.length > 1 && (
          <div className="flex items-center gap-2 mb-4">
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
            <Select value={selectedGroup} onValueChange={setSelectedGroup}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Все группы" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все группы</SelectItem>
                {groups.map((g) => (
                  <SelectItem key={g} value={g}>
                    {g}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Загрузка подключений...
          </div>
        ) : connections.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Database className="mx-auto h-8 w-8 mb-2 opacity-50" />
            <p>Нет подключений</p>
            <p className="text-sm">Добавьте первое подключение к базе данных</p>
          </div>
        ) : (
          <div className="space-y-3">
            {connections.map((conn) => (
              <div
                key={conn.id}
                className="flex items-center justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`flex items-center justify-center w-10 h-10 rounded-lg border ${getDbmsColor(conn.dbms_type)}`}>
                    <span className="text-lg">{getDbmsIcon(conn.dbms_type)}</span>
                  </div>
                  <div>
                    <div className="font-medium">{conn.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {conn.host}:{conn.port}/{conn.database}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      profile: {conn.schema_profile_name || conn.detected_profile_name || "не назначен"}
                    </div>
                  </div>
                  {conn.group && (
                    <Badge variant="outline" className="text-xs">
                      {conn.group}
                    </Badge>
                  )}
                  {conn.schema_profile_name && (
                    <Badge variant="secondary" className="text-xs">
                      {conn.schema_profile_name}
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => testConnection(conn.id)}
                    disabled={testingId === conn.id}
                  >
                    {testingId === conn.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openScenarioGenerationDialog(conn)}
                    title="Профиль схемы и bundle'ы"
                  >
                    <Database className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(conn)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteConnection(conn.id)}
                    className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
