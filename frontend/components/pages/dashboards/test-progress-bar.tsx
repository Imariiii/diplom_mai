"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, Timer } from "lucide-react"

/** Сообщения операций с БД (бэкап, восстановление, индексы) — в одной строке со статусом фазы теста */
const BACKUP_STATUS_LABELS: Record<string, string> = {
  backup_started: "Создание бэкапа БД…",
  backup_completed: "Бэкап создан",
  backup_failed: "Ошибка создания бэкапа",
  restore_started: "Восстановление БД…",
  restore_completed: "БД восстановлена",
  restore_failed: "Ошибка восстановления БД",
  index_creation_started: "Создание индексов сценария…",
  index_creation_completed: "Индексы сценария созданы",
  index_drop_started: "Удаление индексов сценария…",
  index_drop_completed: "Индексы сценария удалены",
  index_drop_failed: "Ошибка удаления индексов",
}

interface TestProgressBarProps {
  progress: number
  elapsedSeconds: number
  statusMessage: string
  backupStatus?: string
  formatTime: (seconds: number) => string
}

export function TestProgressBar({ progress, elapsedSeconds, statusMessage, backupStatus, formatTime }: TestProgressBarProps) {
  const backupLabel =
    backupStatus && BACKUP_STATUS_LABELS[backupStatus]
      ? BACKUP_STATUS_LABELS[backupStatus]
      : backupStatus || null
  const phaseMessage = backupLabel || statusMessage || ""

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

          <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span className="flex shrink-0 items-center gap-1">
              <Timer className="h-3 w-3" />
              Прошло: {formatTime(elapsedSeconds)}
            </span>
            {phaseMessage ? (
              <span className="min-w-0 text-right text-primary">{phaseMessage}</span>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
