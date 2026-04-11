"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Database } from "lucide-react"
import type { DatabaseConnection } from "@/lib/types"

interface DatabaseSelectionCardProps {
  connections: DatabaseConnection[]
  selectedDatabases: string[]
  healthStatus: Record<string, boolean>
  onToggle: (dbId: string) => void
}

export function DatabaseSelectionCard({
  connections,
  selectedDatabases,
  healthStatus,
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

  // Группировка по логической БД
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

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          Выбор СУБД
        </CardTitle>
        <CardDescription>Выберите СУБД-подключения для тестирования</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.map((group) => (
          <div key={group.id ?? "__none__"}>
            {groups.length > 1 && (
              <div className="mb-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {group.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  Профиль: {group.schemaProfileName || "не назначен"}
                </p>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {group.connections.map((conn) => {
                const isConnected = healthStatus[conn.id] !== false
                return (
                  <label
                    key={conn.id}
                    className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                      selectedDatabases.includes(conn.id)
                        ? "border-primary bg-primary/10"
                        : "border-border hover:border-muted-foreground"
                    } ${!isConnected ? "opacity-50" : ""}`}
                  >
                    <Checkbox
                      checked={selectedDatabases.includes(conn.id)}
                      onCheckedChange={() => onToggle(conn.id)}
                      disabled={!isConnected}
                    />
                    <div>
                      <span className="font-medium text-sm">{conn.name}</span>
                      <div className="text-xs text-muted-foreground">
                        {conn.dbms_type} · {conn.host}:{conn.port}
                      </div>
                      {!group.id && (
                        <div className="text-xs text-muted-foreground">
                          Профиль: {conn.schema_profile_name || conn.detected_profile_name || "не назначен"}
                        </div>
                      )}
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
