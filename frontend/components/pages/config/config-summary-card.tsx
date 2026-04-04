"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Query } from "@/lib/api"
import type { Scenario } from "@/lib/types"

interface ConfigSummaryCardProps {
  selectedDatabases: string[]
  testMode: string
  selectedScenario?: Scenario
  selectedQuery?: Query
  useCustomSql: boolean
  virtualUsers: number
  iterations: number
  warmupTime: number
}

const databases = [
  { id: "mysql", name: "MySQL (Sakila)" },
  { id: "postgresql", name: "PostgreSQL (Pagila)" },
]

export function ConfigSummaryCard({
  selectedDatabases,
  testMode,
  selectedScenario,
  selectedQuery,
  useCustomSql,
  virtualUsers,
  iterations,
  warmupTime,
}: ConfigSummaryCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle>Сводка конфигурации</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">СУБД:</span>
            <span className="ml-2 font-medium">
              {selectedDatabases.length > 0
                ? selectedDatabases.map(d => databases.find(db => db.id === d)?.name).join(", ")
                : "Не выбрано"}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Режим:</span>
            <span className="ml-2 font-medium">
              {testMode === "scenario" ? "По сценарию" : "Конкретный запрос"}
            </span>
          </div>
          {testMode === "scenario" ? (
            <div>
              <span className="text-muted-foreground">Сценарий:</span>
              <span className="ml-2 font-medium">{selectedScenario?.name || "Не выбрано"}</span>
            </div>
          ) : (
            <div>
              <span className="text-muted-foreground">Запрос:</span>
              <span className="ml-2 font-medium">
                {useCustomSql
                  ? "Пользовательский SQL"
                  : (selectedQuery?.name || "Не выбрано")}
              </span>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Виртуальных пользователей:</span>
            <span className="ml-2 font-medium">{virtualUsers}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Итераций:</span>
            <span className="ml-2 font-medium">{iterations}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Время прогрева:</span>
            <span className="ml-2 font-medium">{warmupTime} сек</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
