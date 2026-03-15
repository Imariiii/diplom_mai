"use client"

import { useState, useEffect, useCallback } from "react"
import { apiClient } from "@/lib/api"
import type { DatabaseState, RestoreSettings } from "@/lib/types"
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

export function DatabaseStatePanel({ className }: DatabaseStatePanelProps) {
  const [mysqlState, setMysqlState] = useState<DatabaseState | null>(null)
  const [postgresState, setPostgresState] = useState<DatabaseState | null>(null)
  const [settings, setSettings] = useState<RestoreSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<{ [key: string]: boolean }>({})

  const fetchStates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [mysql, postgres, restoreSettings] = await Promise.all([
        apiClient.getDatabaseState("mysql"),
        apiClient.getDatabaseState("postgresql"),
        apiClient.getRestoreSettings()
      ])
      setMysqlState(mysql)
      setPostgresState(postgres)
      setSettings(restoreSettings)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch database states")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStates()
  }, [fetchStates])

  const handleCreateBackup = async (dbType: string) => {
    const key = `backup-${dbType}`
    setActionLoading(prev => ({ ...prev, [key]: true }))
    try {
      await apiClient.createBackup(dbType)
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to create backup for ${dbType}`)
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }))
    }
  }

  const handleRestore = async (dbType: string) => {
    const key = `restore-${dbType}`
    setActionLoading(prev => ({ ...prev, [key]: true }))
    try {
      await apiClient.restoreBackup(dbType)
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to restore ${dbType}`)
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }))
    }
  }

  const handleCleanup = async (dbType: string) => {
    const key = `cleanup-${dbType}`
    setActionLoading(prev => ({ ...prev, [key]: true }))
    try {
      await apiClient.cleanupBackups(dbType)
      await fetchStates()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to cleanup ${dbType}`)
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }))
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

  const DatabaseCard = ({ state, title, icon: Icon }: { state: DatabaseState | null; title: string; icon: any }) => {
    if (!state) return null

    const totalRows = Object.values(state.tables).reduce((sum, t) => sum + t.row_count, 0)

    return (
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon className="w-5 h-5 text-primary" />
              <CardTitle className="text-lg">{title}</CardTitle>
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
              onClick={() => handleCreateBackup(state.dbms_type)}
              disabled={actionLoading[`backup-${state.dbms_type}`]}
            >
              {actionLoading[`backup-${state.dbms_type}`] ? (
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Database className="w-4 h-4 mr-2" />
              )}
              Backup
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleRestore(state.dbms_type)}
              disabled={!state.has_pending_backups || actionLoading[`restore-${state.dbms_type}`]}
            >
              {actionLoading[`restore-${state.dbms_type}`] ? (
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Restore
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCleanup(state.dbms_type)}
              disabled={!state.has_pending_backups || actionLoading[`cleanup-${state.dbms_type}`]}
            >
              {actionLoading[`cleanup-${state.dbms_type}`] ? (
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

        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="mysql">MySQL</TabsTrigger>
            <TabsTrigger value="postgres">PostgreSQL</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <DatabaseCard state={mysqlState} title="MySQL" icon={Database} />
              <DatabaseCard state={postgresState} title="PostgreSQL" icon={Database} />
            </div>

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

          <TabsContent value="mysql" className="mt-4">
            {mysqlState && (
              <div className="space-y-4">
                <DatabaseCard state={mysqlState} title="MySQL" icon={Database} />
                
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Tables</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {Object.entries(mysqlState.tables).map(([table, info]) => (
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
              </div>
            )}
          </TabsContent>

          <TabsContent value="postgres" className="mt-4">
            {postgresState && (
              <div className="space-y-4">
                <DatabaseCard state={postgresState} title="PostgreSQL" icon={Database} />
                
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Tables</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {Object.entries(postgresState.tables).map(([table, info]) => (
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
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
