"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { CheckCircle2, AlertCircle, Database } from "lucide-react"
import type { DatabaseConnection } from "@/lib/types"

interface ConnectionStatusCardProps {
  connections: DatabaseConnection[]
  healthStatus: Record<string, boolean>
}

export function ConnectionStatusCard({ connections, healthStatus }: ConnectionStatusCardProps) {
  if (connections.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Статус подключений
          </CardTitle>
          <CardDescription>Нет настроенных подключений</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          Статус подключений
        </CardTitle>
        <CardDescription>Проверка доступности баз данных</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {connections.map((conn) => {
            const isConnected = healthStatus[conn.id] !== false
            return (
              <div
                key={conn.id}
                className={`flex items-center gap-3 p-4 rounded-lg border ${
                  isConnected ? "border-green-500/50 bg-green-500/10" : "border-red-500/50 bg-red-500/10"
                }`}
              >
                {isConnected ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-500" />
                )}
                <div>
                  <div className="font-medium">{conn.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {conn.host}:{conn.port}/{conn.database}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {isConnected ? "Подключено" : "Не подключено"}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
