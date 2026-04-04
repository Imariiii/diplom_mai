"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Activity } from "lucide-react"

export function EmptyStateCard() {
  return (
    <div className="p-6 flex items-center justify-center h-[calc(100vh-3.5rem)]">
      <Card className="bg-card border-border max-w-md">
        <CardHeader className="text-center">
          <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <CardTitle className="text-foreground">Нет активных тестов</CardTitle>
          <CardDescription>
            Запустите тестирование на странице &quot;Конфигурация и запуск&quot; для отображения дашбордов
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
