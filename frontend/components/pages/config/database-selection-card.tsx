"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Database } from "lucide-react"

interface DatabaseSelectionCardProps {
  selectedDatabases: string[]
  healthStatus: { mysql: boolean; postgresql: boolean }
  onToggle: (dbId: string) => void
}

const databases = [
  { id: "mysql", name: "MySQL (Sakila)" },
  { id: "postgresql", name: "PostgreSQL (Pagila)" },
]

export function DatabaseSelectionCard({ selectedDatabases, healthStatus, onToggle }: DatabaseSelectionCardProps) {
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {databases.map((db) => {
            const isConnected = healthStatus[db.id as keyof typeof healthStatus]
            return (
              <label
                key={db.id}
                className={`flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  selectedDatabases.includes(db.id)
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                } ${!isConnected ? "opacity-50" : ""}`}
              >
                <Checkbox
                  checked={selectedDatabases.includes(db.id)}
                  onCheckedChange={() => onToggle(db.id)}
                  disabled={!isConnected}
                />
                <span className="font-medium">{db.name}</span>
              </label>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
