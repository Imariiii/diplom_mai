"use client"

import { Wifi, WifiOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"

interface PageHeaderProps {
  isConnected: boolean
  currentTest: { status: string } | null
  testName?: string
}

export function PageHeader({ isConnected, currentTest, testName }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-foreground">Дашборды</h1>
        {testName ? (
          <p className="mt-1 truncate text-sm font-medium text-foreground" title={testName}>
            {testName}
          </p>
        ) : null}
        <p className="text-muted-foreground text-pretty break-words">
          Мониторинг производительности в реальном времени
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center gap-1.5">
          {isConnected ? (
            <Wifi className="h-4 w-4 text-green-500" />
          ) : (
            <WifiOff className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-xs text-muted-foreground">
            {isConnected ? "Live" : "Offline"}
          </span>
        </div>

        {currentTest && (
          <Badge
            variant={
              currentTest.status === "running" ? "default" :
              currentTest.status === "cancelling" ? "outline" :
              currentTest.status === "completed" ? "secondary" :
              currentTest.status === "cancelled" ? "outline" :
              currentTest.status === "failed" ? "destructive" : "outline"
            }
          >
            {currentTest.status === "running" ? "Выполняется" :
             currentTest.status === "cancelling" ? "Останавливается" :
             currentTest.status === "completed" ? "Завершён" :
             currentTest.status === "cancelled" ? "Отменён" :
             currentTest.status === "failed" ? "Ошибка" : "Ожидание"}
          </Badge>
        )}
      </div>
    </div>
  )
}
