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

export function DatabaseSelectionCard({ connections, selectedDatabases, healthStatus, onToggle }: DatabaseSelectionCardProps) {
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

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          Выбор СУБД
        </CardTitle>
        <CardDescription>Выберите базы данных для тестирования</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {connections.map((conn) => {
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
                  <span className="font-medium">{conn.name}</span>
                  <div className="text-xs text-muted-foreground">
                    {conn.dbms_type} · {conn.host}:{conn.port}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Профиль: {conn.schema_profile_name || conn.detected_profile_name || "не назначен"}
                  </div>
                </div>
              </label>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
