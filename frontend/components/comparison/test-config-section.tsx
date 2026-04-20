"use client"

import { useState } from "react"
import { Code, Database, Server, Settings, Trophy } from "lucide-react"

import {
  type ComparisonResult,
  type ComparisonTestInfo,
  isPerTestResult,
  isSeriesResult,
} from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"

function getTests(result: ComparisonResult): ComparisonTestInfo[] {
  if (isPerTestResult(result)) return [result.test]
  if (isSeriesResult(result)) return result.tests
  return []
}

function getBaselineId(result: ComparisonResult): string | undefined {
  if (isSeriesResult(result)) return result.baseline_id
  return undefined
}

export function TestConfigSection({ result }: { result: ComparisonResult }) {
  const tests = getTests(result)
  const baselineId = getBaselineId(result)
  const baselineTest = baselineId ? tests.find((t) => t.id === baselineId) : undefined

  return (
    <div className="space-y-3">
      {tests.map((test) => (
        <TestInfoCard
          key={test.id}
          test={test}
          isBaseline={test.id === baselineId}
          baselineConfig={baselineTest?.config}
        />
      ))}
    </div>
  )
}

function TestInfoCard({
  test,
  isBaseline,
  baselineConfig,
}: {
  test: ComparisonTestInfo
  isBaseline: boolean
  baselineConfig?: Record<string, any>
}) {
  const [queriesOpen, setQueriesOpen] = useState(false)
  const config = test.config || {}
  const scenarioName = test.scenario_info?.name || config.scenario || "—"
  const queries = test.scenario_info?.queries || []

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return null
    try {
      return new Date(dateStr).toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateStr
    }
  }

  const diffHighlight = (key: string, value: any) => {
    if (isBaseline || !baselineConfig) return false
    return baselineConfig[key] !== value
  }

  const configRows: Array<[string, string, any]> = [
    ["virtual_users", "Потоки", config.virtual_users ?? config.threads ?? "—"],
    ["iterations", "Итерации", config.iterations ?? "—"],
    ["warmup_time", "Прогрев", config.warmup_time != null ? `${config.warmup_time} с` : "—"],
    ["use_indexes", "Индексы", config.use_indexes ? "Да" : "Нет"],
  ]

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate font-medium">{test.name}</p>
            {isBaseline && (
              <Badge className="gap-1 bg-primary/10 text-primary hover:bg-primary/15 border-transparent">
                <Trophy className="h-3 w-3" />
                Baseline
              </Badge>
            )}
          </div>
          {test.started_at && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {formatDate(test.started_at)}
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        <Settings className="h-3 w-3" />
        Конфигурация
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {configRows.map(([key, label, value]) => (
          <div
            key={key}
            className={`rounded-lg border p-2.5 ${
              diffHighlight(key, config[key])
                ? "border-primary/30 bg-primary/5"
                : "border-border/60 bg-muted/30"
            }`}
          >
            <dt className="text-[11px] text-muted-foreground">{label}</dt>
            <dd
              className={`mt-0.5 font-mono text-sm tabular-nums ${
                diffHighlight(key, config[key]) ? "font-semibold text-primary" : ""
              }`}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        <Database className="h-3 w-3" />
        Сценарий
      </div>
      <div className="mt-2">
        <p className="text-sm font-medium">{scenarioName}</p>
        {test.scenario_info?.description && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {test.scenario_info.description}
          </p>
        )}
      </div>

      {test.connections.length > 0 && (
        <>
          <div className="mt-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            <Server className="h-3 w-3" />
            Подключения
          </div>
          <ul className="mt-2 space-y-1">
            {test.connections.map((conn) => (
              <li
                key={conn.id}
                className="flex flex-wrap items-center gap-2 rounded-md bg-muted/30 px-2.5 py-1.5 text-sm"
              >
                <Badge variant="outline" className="font-mono text-[10px] uppercase">
                  {conn.dbms_type}
                </Badge>
                <span className="font-medium">{conn.name}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {conn.host}:{conn.port}/{conn.database}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {queries.length > 0 && (
        <Collapsible open={queriesOpen} onOpenChange={setQueriesOpen} className="mt-4">
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-2 px-2 text-xs text-primary hover:bg-primary/5"
            >
              <Code className="h-3.5 w-3.5" />
              Запросы сценария ({queries.length})
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {queries.map((q, idx) => (
              <div key={idx} className="rounded-md border border-border bg-background p-2.5">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="font-mono text-[10px] uppercase">
                    {q.query_type}
                  </Badge>
                  <span className="text-xs text-muted-foreground">вес: {q.weight}</span>
                  {q.description && (
                    <span className="text-xs text-muted-foreground">— {q.description}</span>
                  )}
                </div>
                <pre className="mt-1.5 overflow-x-auto rounded bg-muted/60 p-2 text-xs font-mono leading-relaxed whitespace-pre-wrap break-all">
                  {q.sql_template}
                </pre>
              </div>
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
