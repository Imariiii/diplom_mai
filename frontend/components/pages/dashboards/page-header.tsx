"use client"

import { Wifi, WifiOff } from "lucide-react"
import { Badge } from "@/components/ui/badge"

interface PageHeaderProps {
  isConnected: boolean
  currentTest: { status: string } | null
}

export function PageHeader({ isConnected, currentTest }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Дашборды</h1>
        <p className="text-muted-foreground">Мониторинг производительности в реальном времени</p>
      </div>
      <div className="flex items-center gap-3">
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
              currentTest.status === "completed" ? "secondary" :
              currentTest.status === "failed" ? "destructive" : "outline"
            }
          >
            {currentTest.status === "running" ? "Выполняется" :
             currentTest.status === "completed" ? "Завершён" :
             currentTest.status === "failed" ? "Ошибка" : "Ожидание"}
          </Badge>
        )}
      </div>
    </div>
  )
}
