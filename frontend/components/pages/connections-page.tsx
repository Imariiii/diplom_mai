"use client"

import { ConnectionManager } from "./config/connection-manager"

export function ConnectionsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Подключения к СУБД</h1>
        <p className="text-muted-foreground">Управление подключениями к тестируемым СУБД</p>
      </div>

      <ConnectionManager />
    </div>
  )
}
