"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { CheckCircle2, AlertCircle, Database } from "lucide-react"

interface ConnectionStatusCardProps {
  healthStatus: { mysql: boolean; postgresql: boolean }
}

const databases = [
  { id: "mysql", name: "MySQL (Sakila)" },
  { id: "postgresql", name: "PostgreSQL (Pagila)" },
]

export function ConnectionStatusCard({ healthStatus }: ConnectionStatusCardProps) {
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {databases.map((db) => {
            const isConnected = healthStatus[db.id as keyof typeof healthStatus]
            return (
              <div
                key={db.id}
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
                  <div className="font-medium">{db.name}</div>
                  <div className="text-sm text-muted-foreground">
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
