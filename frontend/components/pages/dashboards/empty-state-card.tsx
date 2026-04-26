"use client"

import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Activity } from "lucide-react"

/** Плашка «нет активного прогона» — без внешнего full-viewport блока, рассчитана на размещение внутри родителя с min-w-0 */
export function EmptyStateCard() {
  return (
    <Card className="w-full max-w-lg min-w-0 border-border bg-card shadow-sm">
      <CardHeader className="space-y-4 text-center sm:px-8">
        <div className="mx-auto flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-muted/60">
          <Activity className="h-7 w-7 text-muted-foreground" aria-hidden />
        </div>
        <div className="mx-auto min-w-0 max-w-full space-y-2">
          <CardTitle className="text-balance text-lg text-foreground sm:text-xl">
            Нет активных тестов
          </CardTitle>
          <CardDescription className="text-pretty text-sm leading-relaxed break-words">
            Запустите тестирование на странице «Конфигурация и запуск», чтобы здесь появились дашборды.
          </CardDescription>
        </div>
      </CardHeader>
    </Card>
  )
}
