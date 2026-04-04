"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { TrendingUp, Timer } from "lucide-react"

interface TestProgressBarProps {
  progress: number
  elapsedSeconds: number
  statusMessage: string
  formatTime: (seconds: number) => string
}

export function TestProgressBar({ progress, elapsedSeconds, statusMessage, formatTime }: TestProgressBarProps) {
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
