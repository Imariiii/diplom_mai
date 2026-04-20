"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { FileCode } from "lucide-react"

interface QuerySelectorCardProps {
  customSql: string
  onCustomSqlChange: (sql: string) => void
}

export function QuerySelectorCard({ customSql, onCustomSqlChange }: QuerySelectorCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCode className="h-5 w-5 text-primary" />
          SQL-запрос для тестирования
        </CardTitle>
        <CardDescription>Введите SQL-запрос, который будет использован при нагрузочном тестировании</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Textarea
          placeholder="Введите SQL-запрос для тестирования..."
          value={customSql}
          onChange={(e) => onCustomSqlChange(e.target.value)}
          className="font-mono min-h-[120px]"
        />
        <p className="text-xs text-muted-foreground">
          Поддерживаются SQL-запросы, совместимые с выбранными СУБД
        </p>
      </CardContent>
    </Card>
  )
}
