"use client"

import { useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Code2, Layers } from "lucide-react"
import type { ScenarioBundleSummary, ScenarioTemplate } from "@/lib/types"
import { WorkloadModeBadge } from "@/components/scenarios/workload-mode-badge"

interface ScenarioSelectorCardProps {
  scenarios: ScenarioTemplate[]
  selectedScenarioId: string | undefined
  useIndexes: boolean
  /** Активный набор для выбранного шаблона сценария (запросы и индексы) */
  activeBundle: ScenarioBundleSummary | null
  onScenarioChange: (id: string) => void
  onUseIndexesChange: (value: boolean) => void
}

function formatIndexLine(index: ScenarioBundleSummary["indexes"][0]): string {
  const name = index.index_name?.trim() || "без имени"
  const cols = index.column_names?.trim() || "—"
  return `${name} · ${index.table_name} (${cols})${index.is_unique ? " · уникальный" : ""}`
}

export function ScenarioSelectorCard({
  scenarios,
  selectedScenarioId,
  useIndexes,
  activeBundle,
  onScenarioChange,
  onUseIndexesChange,
}: ScenarioSelectorCardProps) {
  const [sqlDialogOpen, setSqlDialogOpen] = useState(false)

  const indexes = activeBundle?.indexes ?? []
  const isTransactionBundle = activeBundle?.workload_mode === "transaction"
  const queries = useMemo(() => {
    const list = activeBundle?.queries ?? []
    return [...list].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
  }, [activeBundle?.queries])
  const transactions = activeBundle?.transactions ?? []

  const indexesCount = indexes.length

  return (
    <Card className="bg-card border-border">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-primary" />
          Сценарий тестирования
        </CardTitle>
        <CardDescription>
          Шаблон нагрузки и активный набор для выбранной базы. Режим исполнения: одиночные SQL-запросы
          или транзакции — см. бейдж у набора.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="scenario-select">Шаблон сценария</Label>
          <Select value={selectedScenarioId} onValueChange={(value) => onScenarioChange(value)}>
            <SelectTrigger id="scenario-select" className="w-full min-w-0">
              <SelectValue placeholder="Выберите сценарий" />
            </SelectTrigger>
            <SelectContent className="max-h-[min(24rem,70vh)]">
              {(scenarios || []).map((scenario) => (
                <SelectItem key={scenario.id} value={scenario.id} textValue={scenario.name}>
                  <span className="font-medium">{scenario.name}</span>
                </SelectItem>
              ))}
              {(scenarios || []).length === 0 && (
                <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                  Нет доступных сценариев
                </div>
              )}
            </SelectContent>
          </Select>
          {selectedScenarioId && (
            <p className="text-xs text-muted-foreground text-pretty">
              {(scenarios || []).find((s) => s.id === selectedScenarioId)?.description ||
                "Описание шаблона не задано."}
            </p>
          )}
        </div>

        {activeBundle && (
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-sm space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <WorkloadModeBadge workloadMode={activeBundle.workload_mode} className="text-[11px]" />
              <span className="text-muted-foreground">Активный набор:</span>
              <span className="font-medium text-foreground">{activeBundle.name}</span>
            </div>
            {isTransactionBundle && transactions.length > 0 && (
              <span className="text-muted-foreground"> · {transactions.length} транзакций</span>
            )}
            {!isTransactionBundle && queries.length > 0 && (
              <span className="text-muted-foreground"> · {queries.length} запросов</span>
            )}
            {indexesCount > 0 && (
              <span className="text-muted-foreground"> · {indexesCount} индексов</span>
            )}
          </div>
        )}

        {queries.length > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full sm:w-auto"
            onClick={() => setSqlDialogOpen(true)}
          >
            <Code2 className="mr-2 h-4 w-4" />
            Какие SQL-запросы будут выполняться
          </Button>
        )}

        <div className="space-y-3 rounded-lg border border-border bg-background px-3 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <Label htmlFor="use-indexes-switch" className="cursor-pointer">
                Использовать индексы
              </Label>
              <p className="text-xs text-muted-foreground text-pretty">
                Индексы создаются до замеров и удаляются после теста.
              </p>
            </div>
            <Switch
              id="use-indexes-switch"
              checked={useIndexes}
              disabled={indexesCount === 0}
              onCheckedChange={onUseIndexesChange}
            />
          </div>
          {indexesCount > 0 ? (
            <div className="border-t border-border pt-3">
              <p className="text-xs font-medium text-muted-foreground">
                Индексы набора ({indexesCount})
              </p>
              <ul className="mt-2 list-none space-y-1.5 text-xs text-foreground">
                {indexes.map((idx, i) => (
                  <li
                    key={idx.id || `${idx.table_name}-${idx.column_names}-${i}`}
                    className="rounded-md bg-muted/50 px-2 py-1.5 font-mono leading-snug break-all"
                  >
                    {formatIndexLine(idx)}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground border-t border-border pt-3">
              Для этого набора индексы не заданы — переключатель недоступен.
            </p>
          )}
        </div>
      </CardContent>

      <Dialog open={sqlDialogOpen} onOpenChange={setSqlDialogOpen}>
        <DialogContent className="top-[3vh] flex max-h-[min(92vh,48rem)] w-[min(98vw,52rem)] max-w-none translate-y-0 flex-col gap-0 overflow-hidden p-0 sm:max-w-none">
          <DialogHeader className="min-w-0 shrink-0 border-b border-border px-6 py-4 pr-14 text-left">
            <DialogTitle>SQL-запросы набора</DialogTitle>
            <DialogDescription className="text-pretty break-words">
              Тексты шаблонов, которые будут подставляться при нагрузочном тесте (порядок выполнения — по полю
              «порядок»).
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
            <ol className="list-none space-y-4">
              {queries.map((q, i) => (
                <li
                  key={q.id || `q-${i}`}
                  className="rounded-lg border border-border bg-muted/20 p-3"
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      Запрос {i + 1}
                      {typeof q.order_index === "number" ? ` · порядок ${q.order_index}` : ""}
                      {typeof q.weight === "number" ? ` · вес ${q.weight}` : ""}
                    </span>
                    <Badge variant="secondary" className="text-[10px] uppercase">
                      {q.query_type}
                    </Badge>
                  </div>
                  {q.description && (
                    <p className="mb-2 text-xs text-muted-foreground text-pretty">{q.description}</p>
                  )}
                  <pre className="max-h-48 overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-border bg-background p-3 font-mono text-[11px] leading-relaxed">
                    {q.sql_template?.trim() || "—"}
                  </pre>
                </li>
              ))}
            </ol>
          </div>
          <div className="shrink-0 border-t border-border px-6 py-3">
            <Button type="button" variant="secondary" className="w-full sm:w-auto" onClick={() => setSqlDialogOpen(false)}>
              Закрыть
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
