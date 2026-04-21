"use client"

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { FileCode, ShieldAlert } from "lucide-react"

interface QuerySelectorCardProps {
  customSql: string
  onCustomSqlChange: (sql: string) => void
}

const FORBIDDEN_RE = /\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|SHUTDOWN|KILL|RENAME|FLUSH|RESET|PURGE|COPY)\b/i
const ALLOWED_PREFIX_RE = /^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|EXPLAIN)\b/i
const MULTI_STATEMENT_RE = /;\s*\S/

function validateSql(sql: string): string | null {
  const trimmed = sql.trim()
  if (!trimmed) return null
  if (trimmed.length > 10_000) return "Максимальная длина запроса — 10 000 символов"
  if (!ALLOWED_PREFIX_RE.test(trimmed)) return "Запрос должен начинаться с SELECT, INSERT, UPDATE, DELETE, WITH или EXPLAIN"
  if (FORBIDDEN_RE.test(trimmed)) return "Запрос содержит запрещённую конструкцию (DDL / административная команда)"
  if (MULTI_STATEMENT_RE.test(trimmed)) return "Допускается только один SQL-запрос"
  return null
}

export function QuerySelectorCard({ customSql, onCustomSqlChange }: QuerySelectorCardProps) {
  const validationError = useMemo(() => validateSql(customSql), [customSql])

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
          placeholder={"SELECT * FROM film\nWHERE release_year > 2005\nLIMIT 100;"}
          value={customSql}
          onChange={(e) => onCustomSqlChange(e.target.value)}
          className={`font-mono min-h-[120px] ${validationError ? "border-destructive/50 focus-visible:ring-destructive/30" : ""}`}
        />
        {validationError ? (
          <div className="flex items-start gap-1.5 text-xs text-destructive">
            <ShieldAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>{validationError}</span>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Разрешены SELECT, INSERT, UPDATE, DELETE, WITH, EXPLAIN. Запрещены DDL и административные команды.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
