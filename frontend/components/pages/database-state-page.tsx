"use client"

import { DatabaseStatePanel } from "@/components/database-state-panel"

export function DatabaseStatePage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Состояние баз данных</h1>
        <p className="text-muted-foreground">
          Управление резервными копиями и восстановлением тестируемых баз данных
        </p>
      </div>

      <DatabaseStatePanel />
    </div>
  )
}
