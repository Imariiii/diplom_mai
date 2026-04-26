"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Loader2, Database } from "lucide-react"
import type { DatabaseConnection } from "@/lib/types"

export interface ConnectionCheckResult {
  ok: boolean
  message: string
}

interface DatabaseSelectionCardProps {
  connections: DatabaseConnection[]
  selectedDatabases: string[]
  /** Результаты проверки сохранённых подключений; пусто, пока идёт загрузка */
  connectionChecks: Record<string, ConnectionCheckResult>
  checksPending: boolean
  onToggle: (dbId: string) => void
}

export function DatabaseSelectionCard({
  connections,
  selectedDatabases,
  connectionChecks,
  checksPending,
  onToggle,
}: DatabaseSelectionCardProps) {
  if (connections.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Выбор СУБД
          </CardTitle>
          <CardDescription>Сначала добавьте подключения к базам данных</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const groups: {
    id: string | null
    name: string
    schemaProfileName: string | null
    connections: DatabaseConnection[]
  }[] = []
  const seen = new Set<string | null>()

  for (const conn of connections) {
    const gId = conn.logical_database_id || null
    if (!seen.has(gId)) {
      seen.add(gId)
      groups.push({
        id: gId,
        name: conn.logical_database_name || (gId ? gId : "Без базы данных"),
        schemaProfileName: conn.schema_profile_name || conn.detected_profile_name || null,
        connections: [],
      })
    }
    groups.find((g) => g.id === gId)!.connections.push(conn)
  }

  const rowStatus = (connId: string) => {
    if (checksPending) {
      return (
        <span className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />
          Проверка подключения…
        </span>
      )
    }
    const check = connectionChecks[connId]
    if (!check) {
      return <span className="mt-2 text-xs text-muted-foreground">Статус проверки неизвестен</span>
    }
    if (check.ok) {
      return <span className="mt-2 text-xs text-emerald-600 dark:text-emerald-500">{check.message}</span>
    }
    return <span className="mt-2 text-xs text-destructive">{check.message}</span>
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          Выбор СУБД
        </CardTitle>
        <CardDescription>Выберите подключения для теста; для каждого показан результат проверки связи</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.map((group) => (
          <div key={group.id ?? "__none__"}>
            {groups.length > 1 && (
              <div className="mb-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  {group.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  Профиль: {group.schemaProfileName || "не назначен"}
                </p>
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {group.connections.map((conn) => {
                const check = connectionChecks[conn.id]
                const canSelect = !checksPending && check?.ok === true
                return (
                  <label
                    key={conn.id}
                    className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                      selectedDatabases.includes(conn.id)
                        ? "border-primary bg-primary/10"
                        : "border-border hover:border-muted-foreground"
                    } ${!canSelect ? "cursor-not-allowed opacity-80" : ""}`}
                  >
                    <Checkbox
                      checked={selectedDatabases.includes(conn.id)}
                      onCheckedChange={() => onToggle(conn.id)}
                      disabled={!canSelect}
                      className="mt-0.5"
                      aria-describedby={`conn-status-${conn.id}`}
                    />
                    <div className="min-w-0 flex-1">
                      <span className="text-sm font-medium">{conn.name}</span>
                      <div className="text-xs text-muted-foreground">
                        {conn.dbms_type} · {conn.host}:{conn.port}
                      </div>
                      {!group.id && (
                        <div className="text-xs text-muted-foreground">
                          Профиль: {conn.schema_profile_name || conn.detected_profile_name || "не назначен"}
                        </div>
                      )}
                      <div id={`conn-status-${conn.id}`}>{rowStatus(conn.id)}</div>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
