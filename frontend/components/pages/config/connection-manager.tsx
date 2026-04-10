"use client"

import { useState, useEffect } from "react"
import { Plus, Pencil, Trash2, Play, CheckCircle, XCircle, Loader2, Database, FolderOpen } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiClient } from "@/lib/api"
import type {
  ConnectionCreateRequest,
  ConnectionTestResponse,
  DatabaseConnection,
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
                  </div>
                  {conn.group && (
                    <Badge variant="outline" className="text-xs">
                      {conn.group}
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
