"use client"

import type { ReactNode } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { DatabaseConnection, ScenarioTemplate } from "@/lib/types"

interface ConfigSummaryCardProps {
  selectedDatabases: string[]
  testMode: string
  selectedScenario?: ScenarioTemplate
  useIndexes: boolean
  virtualUsers: number
  iterations: number
  warmupTime: number
  connections: DatabaseConnection[]
  selectedProfileName: string | null
  selectedBundleName: string | null
  /** Только сетка полей — для встраивания в диалог (заголовок задаётся снаружи) */
  embedded?: boolean
}

export function ConfigSummaryCard({
  selectedDatabases,
  testMode,
  selectedScenario,
  useIndexes,
  virtualUsers,
  iterations,
  warmupTime,
  connections,
  selectedProfileName,
  selectedBundleName,
  embedded = false,
}: ConfigSummaryCardProps) {
  const row = (label: string, value: ReactNode) => (
    <div className="min-w-0 space-y-0.5">
      <div className="text-muted-foreground">{label}</div>
      <div className="break-words font-medium text-foreground">{value}</div>
    </div>
  )

  const grid = (
    <div className="grid grid-cols-1 gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
      {row(
        "СУБД",
        selectedDatabases.length > 0
          ? selectedDatabases.map((id) => connections.find((connection) => connection.id === id)?.name || id).join(", ")
          : "Не выбрано",
      )}
      {row("Режим", testMode === "scenario" ? "По сценарию" : "Конкретный запрос")}
      {testMode === "scenario" ? (
        <>
          {row("Сценарий", selectedScenario?.name || "Не выбрано")}
          {row("Индексы", useIndexes ? "Включены" : "Выключены")}
          {row("Профиль", selectedProfileName || "Не определён")}
          {row("Bundle", selectedBundleName || "Не разрешён")}
        </>
      ) : (
        row("Запрос", "Пользовательский SQL")
      )}
      {row("Виртуальных пользователей", virtualUsers)}
      {row("Итераций", iterations)}
      {row("Время прогрева", `${warmupTime} сек`)}
    </div>
  )

  if (embedded) {
    return <div className="min-w-0 rounded-lg border border-border bg-muted/20 p-4">{grid}</div>
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle>Сводка конфигурации</CardTitle>
      </CardHeader>
      <CardContent>{grid}</CardContent>
    </Card>
  )
}
