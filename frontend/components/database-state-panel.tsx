"use client"

import { useState, useEffect, useCallback } from "react"
import { apiClient } from "@/lib/api"
import type { DatabaseConnection, DatabaseState, RestoreSettings } from "@/lib/types"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AlertCircle, Database, RefreshCw, Trash2, Settings, CheckCircle, AlertTriangle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

interface DatabaseStatePanelProps {
  className?: string
}

type DatabaseStateMap = Record<string, DatabaseState>

export function DatabaseStatePanel({ className }: DatabaseStatePanelProps) {
  const [connections, setConnections] = useState<DatabaseConnection[]>([])
  const [states, setStates] = useState<DatabaseStateMap>({})
  const [settings, setSettings] = useState<RestoreSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState("overview")
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const [backupIds, setBackupIds] = useState<Record<string, string>>({})

  const fetchStates = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [connectionsResponse, restoreSettings] = await Promise.all([
        apiClient.getConnections(),
        apiClient.getRestoreSettings(),
      ])

      const activeConnections = connectionsResponse.connections
      setConnections(activeConnections)
      setSettings(restoreSettings)

      const stateEntries = await Promise.all(
        activeConnections.map(async (connection) => {
          const state = await apiClient.getDatabaseState(connection.id)
          return [connection.id, state] as const
        })
      )

      setStates(Object.fromEntries(stateEntries))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch database states")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStates()
  }, [fetchStates])

  useEffect(() => {
    if (activeTab === "overview") {
      return
    }

    const hasActiveConnection = connections.some((connection) => connection.id === activeTab)
    if (!hasActiveConnection) {
      setActiveTab("overview")
    }
  }, [activeTab, connections])

  const handleCreateBackup = async (connectionId: string) => {
    const key = `backup-${connectionId}`
    setActionLoading((prev) => ({ ...prev, [key]: true }))
    try {
      const result = await apiClient.createBackup(connectionId)
      if (result?.backup_id) {
        setBackupIds((prev) => ({ ...prev, [connectionId]: result.backup_id }))
      }
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create backup")
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }))
    }
  }

  const handleRestore = async (connectionId: string) => {
    const key = `restore-${connectionId}`
    setActionLoading((prev) => ({ ...prev, [key]: true }))
    try {
      await apiClient.restoreBackup(connectionId, backupIds[connectionId])
      setBackupIds((prev) => {
        const next = { ...prev }
        delete next[connectionId]
        return next
      })
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore database")
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }))
    }
  }

  const handleCleanup = async (connectionId: string) => {
    const key = `cleanup-${connectionId}`
    setActionLoading((prev) => ({ ...prev, [key]: true }))
    try {
      await apiClient.cleanupBackups(connectionId)
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cleanup backups")
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }))
    }
  }

  const handleUpdateSettings = async (updates: Partial<RestoreSettings>) => {
    try {
      await apiClient.updateRestoreSettings(updates)
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update settings")
    }
  }

  const getStatusBadge = (status: DatabaseState["status"]) => {
    switch (status) {
      case "clean":
        return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" /> Clean</Badge>
      case "modified":
        return <Badge variant="destructive"><AlertTriangle className="w-3 h-3 mr-1" /> Modified</Badge>
      case "backup_exists":
        return <Badge variant="secondary"><Database className="w-3 h-3 mr-1" /> Backup Exists</Badge>
      default:
        return <Badge variant="outline">Unknown</Badge>
    }
  }

  const DatabaseCard = ({ connection, state }: { connection: DatabaseConnection; state: DatabaseState }) => {
    const totalRows = Object.values(state.tables).reduce((sum, table) => sum + table.row_count, 0)
    const backupKey = `backup-${connection.id}`
    const restoreKey = `restore-${connection.id}`
    const cleanupKey = `cleanup-${connection.id}`

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              <div>
                <CardTitle className="text-lg">{connection.name}</CardTitle>
                <CardDescription>{connection.dbms_type} • {connection.database}</CardDescription>
              </div>
            </div>
            {getStatusBadge(state.status)}
          </div>
          <CardDescription>
            {Object.keys(state.tables).length} tables • {totalRows.toLocaleString()} total rows
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCreateBackup(connection.id)}
              disabled={actionLoading[backupKey]}
            >
              {actionLoading[backupKey] ? (
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Database className="w-4 h-4 mr-2" />
              )}
              Backup
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleRestore(connection.id)}
              disabled={!state.has_pending_backups || actionLoading[restoreKey]}
            >
              {actionLoading[restoreKey] ? (
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Restore
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCleanup(connection.id)}
              disabled={!state.has_pending_backups || actionLoading[cleanupKey]}
            >
              {actionLoading[cleanupKey] ? (
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Trash2 className="w-4 h-4 mr-2" />
              )}
              Cleanup
            </Button>
          </div>

          {state.has_pending_backups && (
            <Alert variant="default" className="bg-amber-50 border-amber-200">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <AlertDescription className="text-amber-700">
                {state.backup_tables.length} backup table(s) pending
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    )
  }

  const renderTables = (state: DatabaseState) => (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Tables</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {Object.entries(state.tables).map(([table, info]) => (
            <div key={table} className="flex items-center justify-between py-1 border-b last:border-0">
              <span className="font-medium">{table}</span>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{info.row_count.toLocaleString()} rows</span>
                {info.has_backup && <Badge variant="outline" className="text-green-600">Backed up</Badge>}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )

  const overviewStates = connections
    .map((connection) => ({ connection, state: states[connection.id] }))
    .filter((entry) => Boolean(entry.state))

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-primary" />
            <CardTitle>Database State Management</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={fetchStates} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Settings className="w-4 h-4 mr-2" />
                  Settings
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Restore Settings</DialogTitle>
                  <DialogDescription>
                    Configure automatic database restore behavior
                  </DialogDescription>
                </DialogHeader>
                {settings && (
                  <div className="space-y-4 py-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="auto-restore">Auto-restore after tests</Label>
                        <p className="text-sm text-muted-foreground">
                          Automatically restore database after write tests
                        </p>
                      </div>
                      <Switch
                        id="auto-restore"
                        checked={settings.auto_restore}
                        onCheckedChange={(checked) => handleUpdateSettings({ auto_restore: checked })}
                      />
                    </div>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="verify-restore">Verify after restore</Label>
                        <p className="text-sm text-muted-foreground">
                          Verify data integrity after restoration
                        </p>
                      </div>
                      <Switch
                        id="verify-restore"
                        checked={settings.verify_after_restore}
                        onCheckedChange={(checked) => handleUpdateSettings({ verify_after_restore: checked })}
                      />
                    </div>
                    <Separator />
                    <div className="space-y-2">
                      <Label>Backup Strategy</Label>
                      <p className="text-sm text-muted-foreground">
                        Current: <span className="font-medium">{settings.strategy}</span>
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label>Warning Threshold</Label>
                      <p className="text-sm text-muted-foreground">
                        {settings.large_table_warning_threshold.toLocaleString()} rows
                      </p>
                    </div>
                  </div>
                )}
              </DialogContent>
            </Dialog>
          </div>
        </div>
        <CardDescription>
          Manage database backups and automatic restore after tests
        </CardDescription>
      </CardHeader>

      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="flex h-auto w-full flex-wrap justify-start gap-2 bg-transparent p-0">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            {connections.map((connection) => (
              <TabsTrigger key={connection.id} value={connection.id}>
                {connection.name}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="overview" className="mt-4 space-y-4">
            {overviewStates.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2">
                {overviewStates.map(({ connection, state }) => (
                  <DatabaseCard key={connection.id} connection={connection} state={state as DatabaseState} />
                ))}
              </div>
            ) : (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>Нет активных подключений для отображения состояния.</AlertDescription>
              </Alert>
            )}

            {settings && (
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Auto-restore</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      {settings.auto_restore ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-amber-500" />
                      )}
                      <span className={settings.auto_restore ? "text-green-600" : "text-amber-600"}>
                        {settings.auto_restore ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Verify restore</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      {settings.verify_after_restore ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-amber-500" />
                      )}
                      <span className={settings.verify_after_restore ? "text-green-600" : "text-amber-600"}>
                        {settings.verify_after_restore ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Strategy</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Badge variant="secondary" className="uppercase">
                      {settings.strategy}
                    </Badge>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {connections.map((connection) => {
            const state = states[connection.id]
            if (!state) {
              return (
                <TabsContent key={connection.id} value={connection.id} className="mt-4">
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>Состояние подключения пока недоступно.</AlertDescription>
                  </Alert>
                </TabsContent>
              )
            }

            return (
              <TabsContent key={connection.id} value={connection.id} className="mt-4">
                <div className="space-y-4">
                  <DatabaseCard connection={connection} state={state} />
                  {renderTables(state)}
                </div>
              </TabsContent>
            )
          })}
        </Tabs>
      </CardContent>
    </Card>
  )
}
