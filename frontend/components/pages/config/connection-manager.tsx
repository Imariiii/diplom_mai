"use client"

import { useState, useEffect } from "react"
import {
  Plus, Pencil, Trash2, Play, CheckCircle, XCircle, Loader2, Database,
  ChevronDown, ChevronRight, MoreVertical, AlertCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { apiClient } from "@/lib/api"
import type {
  ConnectionProfileAssignRequest,
  ConnectionCreateRequest,
  ConnectionSchemaPreview,
  ConnectionTestResponse,
  DatabaseConnection,
  LogicalDatabase,
  LogicalDatabaseProfileAssignRequest,
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
  mysql: { color: "bg-blue-500/10 text-blue-500 border-blue-500/20", icon: "🐬" },
  mariadb: { color: "bg-violet-500/10 text-violet-500 border-violet-500/20", icon: "🦭" },
  postgresql: { color: "bg-indigo-500/10 text-indigo-500 border-indigo-500/20", icon: "🐘" },
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

type AddMode = "new-db" | "existing-db" | null

function translateConnectionError(raw: string): string {
  const msg = raw.toLowerCase()

  if (msg.includes("connection refused") || msg.includes("errno 111") || msg.includes("could not connect to server")) {
    return "Не удалось подключиться: сервер недоступен. Проверьте хост и порт."
  }
  if (msg.includes("access denied") || msg.includes("authentication failed") || msg.includes("password authentication failed")) {
    return "Ошибка аутентификации: неверное имя пользователя или пароль."
  }
  if (msg.includes("unknown database") || msg.includes("does not exist")) {
    return "База данных не найдена. Проверьте название базы данных."
  }
  if (msg.includes("unknown mysql server host") || msg.includes("could not translate host") || msg.includes("name or service not known") || msg.includes("nodename nor servname")) {
    return "Хост не найден. Проверьте адрес сервера."
  }
  if (msg.includes("timed out") || msg.includes("timeout")) {
    return "Превышено время ожидания подключения. Проверьте хост и порт."
  }
  if (msg.includes("no route to host")) {
    return "Нет маршрута до хоста. Проверьте сетевые настройки."
  }
  if (msg.includes("ssl") || msg.includes("certificate")) {
    return "Ошибка SSL-соединения. Проверьте настройки шифрования."
  }
  if (msg.includes("too many connections") || msg.includes("max_connections")) {
    return "Превышено максимальное число подключений к серверу."
  }

  // Убираем технический префикс, если он есть
  const prefixMatch = raw.match(/^Ошибка подключения:\s*([\s\S]+)$/)
  if (prefixMatch) {
    return `Ошибка подключения. Подробности: ${prefixMatch[1].slice(0, 120)}`
  }

  return raw
}

export function ConnectionManager({ onConnectionsChange }: ConnectionManagerProps) {
  // --- Состояние логических БД ---
  // Только метаданные (id, name, description) — без вложенных connections
  const [logicalDatabases, setLogicalDatabases] = useState<LogicalDatabase[]>([])
  // Полные connections, сгруппированные по logical_database_id
  const [groupedConnections, setGroupedConnections] = useState<Record<string, DatabaseConnection[]>>({})
  const [ungroupedConnections, setUngroupedConnections] = useState<DatabaseConnection[]>([])
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)

  // --- Состояние потока добавления ---
  const [addMode, setAddMode] = useState<AddMode>(null)

  // Шаг 1: создание новой логической БД
  const [newDbDialogOpen, setNewDbDialogOpen] = useState(false)
  const [newDbName, setNewDbName] = useState("")
  const [newDbDescription, setNewDbDescription] = useState("")
  const [creatingDb, setCreatingDb] = useState(false)

  // Шаг 1 (альт): выбор существующей логической БД
  const [selectDbDialogOpen, setSelectDbDialogOpen] = useState(false)
  const [selectedLogicalDbId, setSelectedLogicalDbId] = useState<string>("")

  // Шаг 2: диалог нового/редактирования подключения
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false)
  const [editingConnection, setEditingConnection] = useState<DatabaseConnection | null>(null)
  const [targetLogicalDb, setTargetLogicalDb] = useState<{ id: string; name: string } | null>(null)
  const [groups, setGroups] = useState<string[]>([])
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
  const [testingId, setTestingId] = useState<string | null>(null)

  // --- Диалог профиля/сценариев ---
  const [schemaDialogOpen, setSchemaDialogOpen] = useState(false)
  const [schemaPreviewLogicalDb, setSchemaPreviewLogicalDb] = useState<LogicalDatabase | null>(null)
  const [schemaPreviewConnection, setSchemaPreviewConnection] = useState<DatabaseConnection | null>(null)
  const [schemaPreview, setSchemaPreview] = useState<ConnectionSchemaPreview | null>(null)
  const [availableProfiles, setAvailableProfiles] = useState<SchemaProfileSummary[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)
  const [generatingScenarios, setGeneratingScenarios] = useState(false)
  const [selectedScenarioTypes, setSelectedScenarioTypes] = useState<string[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<string>("")
  const [customProfileName, setCustomProfileName] = useState("")
  const [customProfileDescription, setCustomProfileDescription] = useState("")
  const [compatibilityReportDb, setCompatibilityReportDb] = useState<LogicalDatabase | null>(null)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [logicalResp, connectionsResp] = await Promise.all([
        apiClient.getLogicalDatabases(),
        apiClient.getConnections(),
      ])

      // Сохраняем только метаданные логических БД
      const logicalDbs: LogicalDatabase[] = logicalResp.databases.map((db) => ({
        id: db.id,
        name: db.name,
        description: db.description,
        schema_profile_id: db.schema_profile_id,
        schema_profile_name: db.schema_profile_name,
        reference_connection_id: db.reference_connection_id,
        reference_connection_name: db.reference_connection_name,
        profile_status: db.profile_status,
        compatibility_status: db.compatibility_status,
        compatibility_report: db.compatibility_report,
        validated_at: db.validated_at,
        created_at: db.created_at,
        updated_at: db.updated_at,
      }))
      setLogicalDatabases(logicalDbs)
      setGroups(connectionsResp.groups)

      // Группируем полные connections по logical_database_id
      const grouped: Record<string, DatabaseConnection[]> = {}
      const ungrouped: DatabaseConnection[] = []
      for (const conn of connectionsResp.connections) {
        if (conn.logical_database_id) {
          if (!grouped[conn.logical_database_id]) grouped[conn.logical_database_id] = []
          grouped[conn.logical_database_id].push(conn)
        } else {
          ungrouped.push(conn)
        }
      }
      setGroupedConnections(grouped)
      setUngroupedConnections(ungrouped)

      onConnectionsChange?.(connectionsResp.connections)

      if (openGroups.size === 0 && logicalDbs.length > 0) {
        setOpenGroups(new Set(logicalDbs.map((db) => db.id)))
      }
    } catch (error) {
      console.error("Ошибка загрузки:", error)
      toast.error("Не удалось загрузить данные")
    } finally {
      setLoading(false)
    }
  }

  const toggleGroup = (id: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ===================== Поток добавления =====================

  const handleAddNewDb = () => {
    setAddMode("new-db")
    setNewDbName("")
    setNewDbDescription("")
    setNewDbDialogOpen(true)
  }

  const handleAddToExistingDb = () => {
    setAddMode("existing-db")
    setSelectedLogicalDbId(logicalDatabases[0]?.id || "")
    setSelectDbDialogOpen(true)
  }

  const confirmNewDb = async () => {
    if (!newDbName.trim()) {
      toast.error("Введите название базы данных")
      return
    }
    setCreatingDb(true)
    try {
      const created = await apiClient.createLogicalDatabase({
        name: newDbName.trim(),
        description: newDbDescription.trim() || undefined,
      })
      toast.success(`База данных «${created.name}» создана`)
      setNewDbDialogOpen(false)
      setTargetLogicalDb({ id: created.id, name: created.name })
      openCreateConnectionDialog(created.id, created.name)
      await loadAll()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка создания базы данных")
    } finally {
      setCreatingDb(false)
    }
  }

  const confirmSelectDb = () => {
    const db = logicalDatabases.find((d) => d.id === selectedLogicalDbId)
    if (!db) {
      toast.error("Выберите базу данных")
      return
    }
    setSelectDbDialogOpen(false)
    setTargetLogicalDb({ id: db.id, name: db.name })
    openCreateConnectionDialog(db.id, db.name)
  }

  const openCreateConnectionDialog = (logicalDbId: string, logicalDbName: string) => {
    setEditingConnection(null)
    setTargetLogicalDb({ id: logicalDbId, name: logicalDbName })
    setFormData({
      name: "",
      dbms_type: "mysql",
      host: "localhost",
      port: 3306,
      user: "",
      password: "",
      database: "",
      group: "local",
      logical_database_id: logicalDbId,
    })
    setTestingForm(null)
    setConnectionDialogOpen(true)
  }

  const openEditDialog = (conn: DatabaseConnection) => {
    setEditingConnection(conn)
    setTargetLogicalDb(
      conn.logical_database_id && conn.logical_database_name
        ? { id: conn.logical_database_id, name: conn.logical_database_name }
        : null
    )
    setFormData({
      name: conn.name,
      dbms_type: conn.dbms_type,
      host: conn.host,
      port: conn.port,
      user: conn.user,
      password: "",
      database: conn.database,
      group: conn.group || "local",
      logical_database_id: conn.logical_database_id || undefined,
    })
    setTestingForm(null)
    setConnectionDialogOpen(true)
  }

  const handleDbmsTypeChange = (dbmsType: string) => {
    const typedDbmsType = dbmsType as SupportedDbmsType
    setFormData({ ...formData, dbms_type: typedDbmsType, port: DEFAULT_PORTS[typedDbmsType] })
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
      const displayMessage = result.success ? result.message : translateConnectionError(result.message)
      setTestingForm({ ...result, message: displayMessage })
      if (result.success) toast.success(displayMessage)
      else toast.error(displayMessage)
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Ошибка проверки подключения"
      const displayMessage = translateConnectionError(rawMessage)
      setTestingForm({
        success: false,
        message: displayMessage,
        response_time_ms: null,
      })
      toast.error(displayMessage)
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
          logical_database_id: formData.logical_database_id,
        }
        if (formData.password) updateData.password = formData.password
        await apiClient.updateConnection(editingConnection.id, updateData)
        toast.success("Подключение обновлено")
      } else {
        await apiClient.createConnection(formData)
        toast.success("Подключение создано")
      }
      setConnectionDialogOpen(false)
      loadAll()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка сохранения")
    }
  }

  const deleteConnection = async (id: string) => {
    if (!confirm("Удалить это подключение?")) return
    try {
      await apiClient.deleteConnection(id)
      toast.success("Подключение удалено")
      loadAll()
    } catch {
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
        toast.error(translateConnectionError(result.message))
      }
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Ошибка проверки подключения"
      toast.error(translateConnectionError(rawMessage))
    } finally {
      setTestingId(null)
    }
  }

  const deleteLogicalDatabase = async (id: string, name: string) => {
    if (!confirm(`Удалить базу данных «${name}»? Подключения останутся, но потеряют привязку.`)) return
    try {
      await apiClient.deleteLogicalDatabase(id)
      toast.success(`База данных «${name}» удалена`)
      loadAll()
    } catch {
      toast.error("Ошибка удаления базы данных")
    }
  }

  // ===================== Диалог профиля =====================

  const loadSchemaDialog = async (
    connection: DatabaseConnection,
    logicalDb: LogicalDatabase | null = null
  ) => {
    setSchemaDialogOpen(true)
    setSchemaPreviewLogicalDb(logicalDb)
    setSchemaPreviewConnection(connection)
    setSchemaPreview(null)
    setAvailableProfiles([])
    setSelectedScenarioTypes([])
    setSelectedProfileId(logicalDb?.schema_profile_id || connection.schema_profile_id || "")
    setCustomProfileName(logicalDb?.schema_profile_name || connection.detected_profile_name || "")
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
        logicalDb?.schema_profile_id ||
        connection.schema_profile_id ||
        preview.current_profile?.id ||
        preview.suggested_profile?.existing_profile_id ||
        ""
      )
      setCustomProfileName(
        logicalDb?.schema_profile_name ||
        preview.suggested_profile?.name ||
        connection.detected_profile_name ||
        ""
      )
      setCustomProfileDescription(preview.suggested_profile?.description || "")
      if (preview.total_tables === 0) toast.error("В схеме не найдено пользовательских таблиц")
    } catch (error) {
      console.error("Ошибка загрузки схемы:", error)
      toast.error("Не удалось проанализировать схему БД")
    } finally {
      setSchemaLoading(false)
    }
  }

  const openScenarioGenerationDialog = async (connection: DatabaseConnection) => {
    await loadSchemaDialog(connection, null)
  }

  const openLogicalDatabaseScenarioDialog = async (logicalDb: LogicalDatabase) => {
    const candidates = groupedConnections[logicalDb.id] || []
    const referenceConnection =
      candidates.find((connection) => connection.id === logicalDb.reference_connection_id) ||
      candidates[0]
    if (!referenceConnection) {
      toast.error("Сначала добавьте хотя бы одно подключение в эту базу данных")
      return
    }
    await loadSchemaDialog(referenceConnection, logicalDb)
  }

  const toggleScenarioType = (scenarioType: string, checked: boolean) => {
    setSelectedScenarioTypes((current) => {
      if (checked) return current.includes(scenarioType) ? current : [...current, scenarioType]
      return current.filter((item) => item !== scenarioType)
    })
  }

  const handleSchemaReferenceConnectionChange = async (connectionId: string) => {
    const candidates = schemaPreviewLogicalDb
      ? (groupedConnections[schemaPreviewLogicalDb.id] || [])
      : ungroupedConnections
    const nextConnection = candidates.find((connection) => connection.id === connectionId)
    if (!nextConnection) return
    await loadSchemaDialog(nextConnection, schemaPreviewLogicalDb)
  }

  const assignProfile = async (): Promise<{ schema_profile_id?: string | null } | null> => {
    if (!schemaPreviewConnection) return null
    if (schemaPreviewLogicalDb) {
      const payload: LogicalDatabaseProfileAssignRequest = {
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

      const updated = await apiClient.assignLogicalDatabaseProfile(schemaPreviewLogicalDb.id, payload)
      await loadAll()
      setSchemaPreviewLogicalDb({
        id: updated.id,
        name: updated.name,
        description: updated.description,
        schema_profile_id: updated.schema_profile_id,
        schema_profile_name: updated.schema_profile_name,
        reference_connection_id: updated.reference_connection_id,
        reference_connection_name: updated.reference_connection_name,
        profile_status: updated.profile_status,
        compatibility_status: updated.compatibility_status,
        compatibility_report: updated.compatibility_report,
        validated_at: updated.validated_at,
        created_at: updated.created_at,
        updated_at: updated.updated_at,
      })
      setSelectedProfileId(updated.schema_profile_id || payload.schema_profile_id || "")
      toast.success(`Профиль '${updated.schema_profile_name || payload.profile_name}' назначен для базы данных`)
      return { schema_profile_id: updated.schema_profile_id }
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
    await loadAll()
    setSchemaPreviewConnection(updated)
    setSelectedProfileId(updated.schema_profile_id || payload.schema_profile_id || "")
    toast.success(`Профиль '${updated.schema_profile_name || payload.profile_name}' назначен`)
    return { schema_profile_id: updated.schema_profile_id }
  }

  const generateScenarios = async () => {
    if (!schemaPreviewConnection) return
    if (selectedScenarioTypes.length === 0) {
      toast.error("Выберите хотя бы один тип сценария")
      return
    }
    setGeneratingScenarios(true)
    try {
      const updatedTarget = await assignProfile()
      const profileId = updatedTarget?.schema_profile_id
      if (!profileId) throw new Error("Не удалось определить профиль для генерации сценариев")

      const result = schemaPreviewLogicalDb
        ? await apiClient.generateLogicalDatabaseBundles(schemaPreviewLogicalDb.id, {
            reference_connection_id: schemaPreviewConnection.id,
            scenario_template_ids: selectedScenarioTypes,
          })
        : await apiClient.generateProfileBundles(profileId, {
            reference_connection_id: schemaPreviewConnection.id,
            scenario_template_ids: selectedScenarioTypes,
          })

      toast.success(`Сгенерировано сценариев: ${result.generated_count}`)
      await loadAll()
      setSchemaDialogOpen(false)
    } catch (error) {
      console.error("Ошибка генерации сценариев:", error)
      toast.error(error instanceof Error ? error.message : "Не удалось сгенерировать сценарии")
    } finally {
      setGeneratingScenarios(false)
    }
  }

  const validateLogicalDatabase = async (logicalDb: LogicalDatabase) => {
    try {
      const report = await apiClient.validateLogicalDatabase(logicalDb.id, {
        reference_connection_id: logicalDb.reference_connection_id || undefined,
        mode: "strict",
      })
      await loadAll()
      if (report.valid) {
        toast.success(report.warnings.length > 0
          ? "Совместимость подтверждена с предупреждениями"
          : "Совместимость logical database подтверждена")
      } else {
        toast.error(report.errors[0] || "Logical database несовместима")
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось проверить совместимость")
    }
  }

  const confirmConnectionProfile = async (conn: DatabaseConnection) => {
    if (!conn.logical_database_id) return
    try {
      const updated = await apiClient.confirmLogicalDatabaseConnectionProfile(
        conn.logical_database_id,
        conn.id
      )
      await loadAll()
      if (updated.compatibility_status !== "invalid") {
        toast.success("Schema profile подключения подтверждён")
      } else {
        toast.error(
          updated.compatibility_report?.errors?.[0] ||
          "Подключение несовместимо с logical database"
        )
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Не удалось подтвердить schema profile")
    }
  }

  const getDbmsColor = (dbmsType: string) =>
    DBMS_STYLES[dbmsType as SupportedDbmsType]?.color || DBMS_STYLES.mysql.color
  const getDbmsIcon = (dbmsType: string) =>
    DBMS_STYLES[dbmsType as SupportedDbmsType]?.icon || DBMS_STYLES.mysql.icon
  const formatCompatibilityStatus = (status?: string | null) => {
    if (status === "valid") return "совместима"
    if (status === "valid_with_warnings") return "совместима с предупреждениями"
    if (status === "invalid") return "несовместима"
    return "не проверена"
  }
  const compatibilityErrors = compatibilityReportDb?.compatibility_report?.errors || []
  const compatibilityWarnings = compatibilityReportDb?.compatibility_report?.warnings || []

  // ===================== Рендер строки подключения =====================

  const renderConnectionRow = (conn: DatabaseConnection) => (
    <div
      key={conn.id}
      className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className={`flex items-center justify-center w-9 h-9 rounded-lg border ${getDbmsColor(conn.dbms_type)}`}>
          <span className="text-base">{getDbmsIcon(conn.dbms_type)}</span>
        </div>
        <div>
          <div className="font-medium text-sm">{conn.name}</div>
          <div className="text-xs text-muted-foreground">
            {conn.host}:{conn.port}/{conn.database}
          </div>
          <div className="text-xs text-muted-foreground">
            профиль: {conn.schema_profile_name || conn.detected_profile_name || "не назначен"}
            {conn.logical_database_id
              ? conn.profile_source === "pending_review"
                ? " · требует подтверждения"
                : " · подтверждён"
              : ""}
          </div>
        </div>
        {conn.group && (
          <Badge variant="outline" className="text-xs">{conn.group}</Badge>
        )}
        {conn.schema_profile_name && (
          <Badge variant="secondary" className="text-xs">{conn.schema_profile_name}</Badge>
        )}
      </div>

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => testConnection(conn.id)}
          disabled={testingId === conn.id}
          title="Проверить подключение"
        >
          {testingId === conn.id ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
        </Button>
        {!conn.logical_database_id && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => openScenarioGenerationDialog(conn)}
            title="Профиль схемы и сценарии"
          >
            <Database className="h-4 w-4" />
          </Button>
        )}
        {conn.logical_database_id && conn.profile_source === "pending_review" && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { void confirmConnectionProfile(conn) }}
            title="Подтвердить schema profile"
          >
            <CheckCircle className="h-4 w-4" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => openEditDialog(conn)}
          title="Редактировать"
        >
          <Pencil className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => deleteConnection(conn.id)}
          className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
          title="Удалить"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )

  // ===================== JSX =====================

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Подключение к СУБД
              </CardTitle>
              <CardDescription>Управление подключениями к тестируемым СУБД</CardDescription>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Добавить
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleAddNewDb}>
                  <Plus className="mr-2 h-4 w-4" />
                  Добавить новую базу данных
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={handleAddToExistingDb}
                  disabled={logicalDatabases.length === 0}
                >
                  <Database className="mr-2 h-4 w-4" />
                  Добавить к существующей базе данных
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Загрузка...
            </div>
          ) : logicalDatabases.length === 0 && ungroupedConnections.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Database className="mx-auto h-8 w-8 mb-2 opacity-50" />
              <p>Нет баз данных</p>
              <p className="text-sm">Добавьте первую базу данных через кнопку «Добавить»</p>
            </div>
          ) : (
            <div className="space-y-2">
              {/* Сгруппированные подключения */}
              {logicalDatabases.map((logicalDb) => {
                const dbConnections = groupedConnections[logicalDb.id] || []
                return (
                  <Collapsible
                    key={logicalDb.id}
                    open={openGroups.has(logicalDb.id)}
                    onOpenChange={() => toggleGroup(logicalDb.id)}
                  >
                    <div className="rounded-lg border bg-muted/30">
                      <div className="flex items-center justify-between px-4 py-3">
                        <CollapsibleTrigger asChild>
                          <button className="flex items-center gap-2 text-left flex-1 min-w-0">
                            {openGroups.has(logicalDb.id) ? (
                              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                            )}
                            <Database className="h-4 w-4 shrink-0 text-primary" />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="font-medium truncate">{logicalDb.name}</span>
                                {logicalDb.schema_profile_name && (
                                  <Badge variant="secondary" className="text-[10px] shrink-0">
                                    {logicalDb.schema_profile_name}
                                  </Badge>
                                )}
                                <Badge
                                  variant={logicalDb.compatibility_status === "invalid" ? "destructive" : "outline"}
                                  className="text-[10px] shrink-0"
                                >
                                  {formatCompatibilityStatus(logicalDb.compatibility_status)}
                                </Badge>
                              </div>
                              <div className="text-xs text-muted-foreground truncate hidden sm:block">
                                Reference: {logicalDb.reference_connection_name || "не выбран"}
                              </div>
                              {logicalDb.description && (
                                <div className="text-xs text-muted-foreground truncate hidden sm:block">
                                  {logicalDb.description}
                                </div>
                              )}
                            </div>
                            <Badge variant="outline" className="text-xs shrink-0">
                              {dbConnections.length}
                            </Badge>
                          </button>
                        </CollapsibleTrigger>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0 shrink-0">
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => { void openLogicalDatabaseScenarioDialog(logicalDb) }}
                              disabled={dbConnections.length === 0}
                            >
                              <Database className="mr-2 h-4 w-4" />
                              Профиль и сценарии тестирования
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => { void validateLogicalDatabase(logicalDb) }}
                              disabled={dbConnections.length === 0}
                            >
                              <CheckCircle className="mr-2 h-4 w-4" />
                              Проверить совместимость
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setCompatibilityReportDb(logicalDb)}
                              disabled={!logicalDb.compatibility_report}
                            >
                              <AlertCircle className="mr-2 h-4 w-4" />
                              Отчёт совместимости
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => {
                                setTargetLogicalDb({ id: logicalDb.id, name: logicalDb.name })
                                openCreateConnectionDialog(logicalDb.id, logicalDb.name)
                              }}
                            >
                              <Plus className="mr-2 h-4 w-4" />
                              Добавить подключение
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-red-500 focus:text-red-500"
                              onClick={() => deleteLogicalDatabase(logicalDb.id, logicalDb.name)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Удалить базу данных
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>

                      <CollapsibleContent>
                        <div className="px-4 pb-3 space-y-2">
                          {dbConnections.length === 0 ? (
                            <p className="text-xs text-muted-foreground py-2">
                              Нет подключений. Добавьте через меню ⋮
                            </p>
                          ) : (
                            dbConnections.map(renderConnectionRow)
                          )}
                        </div>
                      </CollapsibleContent>
                    </div>
                  </Collapsible>
                )
              })}

              {/* Подключения без логической БД */}
              {ungroupedConnections.length > 0 && (
                <Collapsible
                  open={openGroups.has("__ungrouped__")}
                  onOpenChange={() => toggleGroup("__ungrouped__")}
                >
                  <div className="rounded-lg border bg-muted/10">
                    <CollapsibleTrigger asChild>
                      <button className="flex items-center gap-2 w-full text-left px-4 py-3">
                        {openGroups.has("__ungrouped__") ? (
                          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        )}
                        <span className="font-medium text-muted-foreground">Без базы данных</span>
                        <Badge variant="outline" className="text-xs">
                          {ungroupedConnections.length}
                        </Badge>
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-4 pb-3 space-y-2">
                        {ungroupedConnections.map(renderConnectionRow)}
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== Диалог: Новая логическая БД ===== */}
      <Dialog open={newDbDialogOpen} onOpenChange={setNewDbDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Новая база данных</DialogTitle>
            <DialogDescription>
              Укажите название датасета / модели данных. Затем добавите первое подключение к СУБД.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new-db-name">Название</Label>
              <Input
                id="new-db-name"
                value={newDbName}
                onChange={(e) => setNewDbName(e.target.value)}
                placeholder="Например: Sakila"
                onKeyDown={(e) => e.key === "Enter" && confirmNewDb()}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-db-desc">Описание (необязательно)</Label>
              <Input
                id="new-db-desc"
                value={newDbDescription}
                onChange={(e) => setNewDbDescription(e.target.value)}
                placeholder="Краткое описание модели данных"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewDbDialogOpen(false)} disabled={creatingDb}>
              Отмена
            </Button>
            <Button onClick={confirmNewDb} disabled={creatingDb}>
              {creatingDb ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Далее
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== Диалог: Выбор существующей логической БД ===== */}
      <Dialog open={selectDbDialogOpen} onOpenChange={setSelectDbDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Выбор базы данных</DialogTitle>
            <DialogDescription>
              Выберите базу данных, к которой нужно добавить новое СУБД-подключение.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-3">
            {logicalDatabases.map((db) => (
              <label
                key={db.id}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedLogicalDbId === db.id
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <input
                  type="radio"
                  name="logical-db-select"
                  value={db.id}
                  checked={selectedLogicalDbId === db.id}
                  onChange={() => setSelectedLogicalDbId(db.id)}
                  className="accent-primary"
                />
                <div>
                  <div className="font-medium text-sm">{db.name}</div>
                  {db.description && (
                    <div className="text-xs text-muted-foreground">{db.description}</div>
                  )}
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {(groupedConnections[db.id]?.length ?? 0)} подключений
                  </div>
                </div>
              </label>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectDbDialogOpen(false)}>
              Отмена
            </Button>
            <Button onClick={confirmSelectDb} disabled={!selectedLogicalDbId}>
              Далее
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== Диалог: Создать / редактировать подключение ===== */}
      <Dialog open={connectionDialogOpen} onOpenChange={setConnectionDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingConnection ? "Редактировать подключение" : "Новое подключение"}
            </DialogTitle>
            <DialogDescription>
              {targetLogicalDb ? (
                <>
                  База данных: <span className="font-medium">{targetLogicalDb.name}</span>
                </>
              ) : (
                editingConnection
                  ? "Измените параметры подключения к СУБД"
                  : "Добавьте подключение к СУБД"
              )}
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
                  placeholder="Например: Sakila MySQL"
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
                <Label htmlFor="group">Среда</Label>
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
            <Button variant="outline" onClick={testFormConnection} disabled={testingFormLoading}>
              {testingFormLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Проверить
            </Button>
            <Button onClick={saveConnection}>
              {editingConnection ? "Сохранить" : "Создать"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== Диалог: Профиль схемы и сценарии ===== */}
      <Dialog open={schemaDialogOpen} onOpenChange={setSchemaDialogOpen}>
        <DialogContent className="top-[3vh] flex max-h-[94vh] w-[min(98vw,92rem)] max-w-none translate-y-0 flex-col gap-0 overflow-hidden p-0 sm:max-w-none">
          <DialogHeader className="shrink-0 px-6 pt-6 pr-14">
            <DialogTitle>
              {schemaPreviewLogicalDb
                ? `Профиль схемы и сценарии для «${schemaPreviewLogicalDb.name}»`
                : `Профиль схемы и сценарии для «${schemaPreviewConnection?.name || "подключения"}»`}
            </DialogTitle>
            <DialogDescription>
              {schemaPreviewLogicalDb
                ? "Подтвердите профиль для базы данных и выберите эталонное подключение для генерации сценариев"
                : "Подтвердите или переопределите профиль схемы, затем сгенерируйте сценарии тестирования"}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-6">
            <div className="space-y-4 py-4">
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
                    {schemaPreviewLogicalDb && (
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="rounded-lg bg-muted/50 p-3">
                          <div className="text-sm text-muted-foreground">База данных</div>
                          <div className="font-medium">{schemaPreviewLogicalDb.name}</div>
                          <div className="text-xs text-muted-foreground mt-1">
                            {schemaPreviewLogicalDb.description || "Без описания"}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label>Эталонное подключение</Label>
                          <Select
                            value={schemaPreviewConnection?.id || ""}
                            onValueChange={(value) => { void handleSchemaReferenceConnectionChange(value) }}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Выберите подключение" />
                            </SelectTrigger>
                            <SelectContent>
                              {(groupedConnections[schemaPreviewLogicalDb.id] || []).map((connection) => (
                                <SelectItem key={connection.id} value={connection.id}>
                                  {connection.name} · {connection.dbms_type}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    )}

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg bg-muted/50 p-3">
                        <div className="text-sm text-muted-foreground">Текущий профиль</div>
                        <div className="font-medium">
                          {schemaPreviewLogicalDb?.schema_profile_name ||
                            schemaPreview.current_profile?.name ||
                            schemaPreviewConnection?.schema_profile_name ||
                            "не назначен"}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {schemaPreview.current_profile?.description ||
                            (schemaPreviewLogicalDb
                              ? "Профиль задаётся на уровне базы данных"
                              : "Пока профиль не подтверждён вручную")}
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
                        <Select
                          value={selectedProfileId || "custom"}
                          onValueChange={(value) => setSelectedProfileId(value === "custom" ? "" : value)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Выберите профиль или создайте новый" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="custom">Создать / использовать предложенный</SelectItem>
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
                    <Label>Типы сценариев для генерации</Label>
                    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                      {GENERATABLE_SCENARIO_TYPES.map((scenarioType) => {
                        const available = schemaPreview.available_scenario_types.includes(scenarioType.value)
                        const checked = selectedScenarioTypes.includes(scenarioType.value)
                        return (
                          <label
                            key={scenarioType.value}
                            className={`flex items-start gap-3 rounded-lg border p-3 ${available ? "cursor-pointer" : "opacity-50"}`}
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
                    <div className="rounded-lg border p-3">
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
                        {schemaPreview.tables.map((table) => (
                          <div key={table.name} className="rounded-lg border bg-muted/20 p-3">
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
                              Шаблоны:{" "}
                              {schemaPreview.matching_templates[table.name]?.length
                                ? schemaPreview.matching_templates[table.name]
                                    .map((tId) => TEMPLATE_LABELS[tId] || tId)
                                    .join(", ")
                                : "нет подходящих"}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-sm text-muted-foreground">
                  Не удалось загрузить превью схемы.
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="border-t px-6 py-4 shrink-0">
            <Button variant="outline" onClick={() => setSchemaDialogOpen(false)} disabled={generatingScenarios}>
              Отмена
            </Button>
            <Button
              variant="outline"
              onClick={() => { void assignProfile() }}
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
              Сгенерировать сценарии
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(compatibilityReportDb)} onOpenChange={(open) => !open && setCompatibilityReportDb(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Отчёт совместимости</DialogTitle>
            <DialogDescription>
              {compatibilityReportDb?.name} · {formatCompatibilityStatus(compatibilityReportDb?.compatibility_status)}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid gap-2 rounded-lg border bg-muted/30 p-3 text-sm sm:grid-cols-2">
              <div>
                <div className="text-muted-foreground">Reference connection</div>
                <div className="font-medium">{compatibilityReportDb?.reference_connection_name || "не выбран"}</div>
              </div>
              <div>
                <div className="text-muted-foreground">Режим проверки</div>
                <div className="font-medium">{compatibilityReportDb?.compatibility_report?.mode || "unknown"}</div>
              </div>
            </div>

            <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
              <div>
                <div className="mb-2 font-medium text-sm">
                  Ошибки ({compatibilityErrors.length})
                </div>
                {compatibilityErrors.length > 0 ? (
                  <ul className="space-y-2 text-sm text-red-700">
                    {compatibilityErrors.map((error) => (
                      <li key={error} className="rounded-md border border-red-500/30 bg-red-500/10 p-2">
                        {error}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="rounded-md border bg-muted/20 p-2 text-sm text-muted-foreground">
                    Ошибок совместимости нет.
                  </div>
                )}
              </div>

              <div>
                <div className="mb-2 font-medium text-sm">
                  Предупреждения ({compatibilityWarnings.length})
                </div>
                {compatibilityWarnings.length > 0 ? (
                  <ul className="space-y-2 text-sm text-amber-700">
                    {compatibilityWarnings.map((warning) => (
                      <li key={warning} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2">
                        {warning}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="rounded-md border bg-muted/20 p-2 text-sm text-muted-foreground">
                    Предупреждений нет.
                  </div>
                )}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCompatibilityReportDb(null)}>
              Закрыть
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
