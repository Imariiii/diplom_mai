"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { FileCode, Edit3 } from "lucide-react"
import type { Query } from "@/lib/api"

interface QuerySelectorCardProps {
  queries: Query[]
  selectedQueryId: string | undefined
  useCustomSql: boolean
  customSql: string
  onQueryChange: (id: string) => void
  onCustomSqlChange: (sql: string) => void
  onToggleCustom: (useCustom: boolean) => void
}

export function QuerySelectorCard({
  queries,
  selectedQueryId,
  useCustomSql,
  customSql,
  onQueryChange,
  onCustomSqlChange,
  onToggleCustom,
}: QuerySelectorCardProps) {
  const selectedQuery = queries?.find(q => q.id === selectedQueryId)

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCode className="h-5 w-5 text-primary" />
          SQL-запрос для тестирования
        </CardTitle>
        <CardDescription>Выберите запрос из списка или введите свой</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button
            variant={!useCustomSql ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleCustom(false)}
          >
            <FileCode className="h-4 w-4 mr-2" />
            Из списка
          </Button>
          <Button
            variant={useCustomSql ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleCustom(true)}
          >
            <Edit3 className="h-4 w-4 mr-2" />
            Свой запрос
          </Button>
        </div>

        {!useCustomSql ? (
          <>
            <Select
              value={selectedQueryId}
              onValueChange={onQueryChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Выберите запрос" />
              </SelectTrigger>
              <SelectContent>
                {queries.map((query) => (
                  <SelectItem key={query.id} value={query.id}>
                    {query.name} - {query.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedQuery && (
              <div className="p-3 bg-muted rounded-lg">
                <div className="text-sm text-muted-foreground mb-2">{selectedQuery.description}</div>
                <pre className="text-sm overflow-x-auto font-mono">
                  {selectedQuery.sql}
                </pre>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-2">
            <Textarea
              placeholder="Введите SQL-запрос для тестирования..."
              value={customSql}
              onChange={(e) => onCustomSqlChange(e.target.value)}
              className="font-mono min-h-[120px]"
            />
            <div className="text-xs text-muted-foreground">
              Поддерживаются SQL-запросы, совместимые с выбранными СУБД
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
