"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, Timer, Database } from "lucide-react"

const BACKUP_STATUS_LABELS: Record<string, string> = {
  backup_started: "Создание бэкапа БД...",
  backup_completed: "Бэкап создан",
  restore_started: "Восстановление БД...",
  restore_completed: "БД восстановлена",
}

interface TestProgressBarProps {
  progress: number
  elapsedSeconds: number
  statusMessage: string
  backupStatus?: string
  formatTime: (seconds: number) => string
}

export function TestProgressBar({ progress, elapsedSeconds, statusMessage, backupStatus, formatTime }: TestProgressBarProps) {
  const backupLabel = backupStatus ? BACKUP_STATUS_LABELS[backupStatus] : null

  return (
    <Card className="bg-card border-border">
      <CardContent className="pt-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary animate-pulse" />
              <span className="font-medium">Прогресс тестирования</span>
            </div>
            <span className="font-mono text-primary">{progress.toFixed(1)}%</span>
          </div>

          <Progress value={progress} className="h-2" />

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <Timer className="h-3 w-3" />
                Прошло: {formatTime(elapsedSeconds)}
              </span>
              {backupLabel && (
                <span className="flex items-center gap-1 text-amber-600">
                  <Database className="h-3 w-3 animate-pulse" />
                  {backupLabel}
                </span>
              )}
            </div>
            {statusMessage && (
              <span className="text-primary">{statusMessage}</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
