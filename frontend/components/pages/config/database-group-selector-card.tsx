"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Database } from "lucide-react"
import type { DatabaseGroupWithConnections } from "@/lib/types"
import { useAppStore } from "@/lib/store"

interface DatabaseGroupSelectorCardProps {
  databases: DatabaseGroupWithConnections[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function connectionCountLabel(count: number): string {
  if (count === 1) return "1 подключение"
  if (count >= 2 && count <= 4) return `${count} подключения`
  return `${count} подключений`
}

export function DatabaseGroupSelectorCard({ databases, selectedId, onSelect }: DatabaseGroupSelectorCardProps) {
  const { setCurrentPage } = useAppStore()

  if (databases.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Группа баз данных
          </CardTitle>
          <CardDescription>
            Нет настроенных групп баз данных.{" "}
            <button
              onClick={() => setCurrentPage("connections")}
              className="underline text-primary hover:opacity-80"
            >
              Добавьте подключения
            </button>{" "}
            на странице «Подключения к СУБД».
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          Группа баз данных
        </CardTitle>
        <CardDescription>
          Выберите группу совместимых баз данных для нагрузочного тестирования
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {databases.map((db) => (
            <button
              key={db.id}
              onClick={() => onSelect(db.id)}
              className={`p-4 rounded-lg border text-left transition-colors ${
                selectedId === db.id
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-muted-foreground"
              }`}
            >
              <div className="font-medium text-sm">{db.name}</div>
              {db.description && (
                <div className="text-xs text-muted-foreground mt-1">{db.description}</div>
              )}
              <div className="text-xs text-muted-foreground mt-1">
                {connectionCountLabel(db.connections.length)}
              </div>
              {db.schema_profile_name && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  Профиль: {db.schema_profile_name}
                </div>
              )}
              <div className="text-xs text-muted-foreground mt-0.5">
                Reference: {db.reference_connection_name || "не выбран"}
              </div>
              <div className={`text-xs mt-0.5 ${
                db.compatibility_status === "invalid" ? "text-red-600" : "text-muted-foreground"
              }`}>
                Совместимость: {db.compatibility_status || "unknown"}
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
