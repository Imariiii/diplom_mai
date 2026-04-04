"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Copy, Trash2, Edit, Code, ChevronRight, ChevronDown, Hash, X, AlertCircle, Plus } from "lucide-react"
import type { Scenario, ScenarioQuery } from "@/lib/types"

const PARAM_TYPES = [
  { value: "random_int", label: "Случайное целое число" },
  { value: "random_from_table", label: "Случайное значение из таблицы" },
  { value: "sequential_int", label: "Последовательное целое" },
  { value: "uuid", label: "UUID" },
  { value: "fixed", label: "Фиксированное значение" },
  { value: "random_string", label: "Случайная строка" },
  { value: "random_date", label: "Случайная дата" },
]

interface QueryCardProps {
  query: ScenarioQuery
  index: number
  isExpanded: boolean
  onToggle: () => void
  onDelete: () => void
  onAddParam: () => void
  onDeleteParam: (paramId: string) => void
  extractParamsFromSql: (sql: string) => string[]
}

function QueryCard({ query, index, isExpanded, onToggle, onDelete, onAddParam, onDeleteParam, extractParamsFromSql }: QueryCardProps) {
  const params = extractParamsFromSql(query.sql_template)

  return (
    <div className="border rounded-lg overflow-hidden">
      <div
        className="p-4 bg-muted/50 flex items-center justify-between cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          <Badge variant={query.query_type === 'select' ? 'default' : 'secondary'}>
            {query.query_type.toUpperCase()}
          </Badge>
          <span className="font-medium">Запрос #{index + 1}</span>
          <Badge variant="outline" className="text-xs">
            weight: {query.weight}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
        >
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4">
          {query.description && (
            <p className="text-sm text-muted-foreground">
              {query.description}
            </p>
          )}

          <div className="bg-muted p-3 rounded-md">
            <pre className="text-sm overflow-x-auto">
              <code>{query.sql_template}</code>
            </pre>
          </div>

          {params.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <Hash className="h-4 w-4" />
                  Параметры ({query.params?.length || 0}/{params.length})
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onAddParam}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Добавить
                </Button>
              </div>

              {query.params && query.params.length > 0 ? (
                <div className="space-y-2">
                  {query.params.map((param) => (
                    <div
                      key={param.id}
                      className="flex items-center justify-between p-2 bg-muted/50 rounded"
                    >
                      <div className="flex items-center gap-2">
                        <code className="text-sm bg-primary/10 px-2 py-0.5 rounded">
                          {param.param_name}
                        </code>
                        <Badge variant="outline" className="text-xs">
                          {PARAM_TYPES.find(t => t.value === param.param_type)?.label || param.param_type}
                        </Badge>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => onDeleteParam(param.id)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <Alert variant="destructive" className="py-2">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="text-xs">
                    Не все параметры настроены. Нажмите "Добавить" для настройки.
                  </AlertDescription>
                </Alert>
              )}

              {query.params && params.map(paramName => {
                const isConfigured = query.params!.some(p => p.param_name === paramName)
                if (isConfigured) return null
                return (
                  <div key={paramName} className="flex items-center gap-2 text-amber-600 text-sm">
                    <AlertCircle className="h-4 w-4" />
                    <code className="bg-amber-100 px-1 rounded">{paramName}</code>
                    <span>не настроен</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface ScenarioDetailPanelProps {
  selectedScenario: Scenario
  queries: ScenarioQuery[]
  expandedQueries: Set<string>
  onClone: () => void
  onEdit: () => void
  onDelete: () => void
  onAddQuery: () => void
  onDeleteQuery: (queryId: string) => void
  onToggleQuery: (queryId: string) => void
  onAddParam: (queryId: string) => void
  onDeleteParam: (queryId: string, paramId: string) => void
  extractParamsFromSql: (sql: string) => string[]
}

export function ScenarioDetailPanel({
  selectedScenario,
  queries,
  expandedQueries,
  onClone,
  onEdit,
  onDelete,
  onAddQuery,
  onDeleteQuery,
  onToggleQuery,
  onAddParam,
  onDeleteParam,
  extractParamsFromSql,
}: ScenarioDetailPanelProps) {
  return (
    <>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">{selectedScenario.name}</h3>
            {selectedScenario.is_builtin === 't' && (
              <Badge variant="secondary">built-in</Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {selectedScenario.scenario_type}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={onClone} title="Клонировать">
            <Copy className="h-4 w-4" />
          </Button>
          {selectedScenario.is_builtin !== 't' && (
            <>
              <Button variant="outline" size="icon" onClick={onEdit} title="Редактировать">
                <Edit className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" onClick={onDelete} title="Удалить">
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </>
          )}
        </div>
      </div>
      {selectedScenario.description && (
        <p className="text-sm text-muted-foreground mt-2">
          {selectedScenario.description}
        </p>
      )}

      <Tabs defaultValue="queries" className="mt-4">
        <TabsList>
          <TabsTrigger value="queries" className="flex items-center gap-2">
            <Code className="h-4 w-4" />
            Запросы ({queries.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="queries" className="space-y-4">
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={onAddQuery}>
              <Plus className="mr-2 h-4 w-4" />
              Добавить запрос
            </Button>
          </div>

          <ScrollArea className="h-[400px]">
            <div className="space-y-4">
              {queries.map((query, index) => (
                <QueryCard
                  key={query.id}
                  query={query}
                  index={index}
                  isExpanded={expandedQueries.has(query.id)}
                  onToggle={() => onToggleQuery(query.id)}
                  onDelete={() => onDeleteQuery(query.id)}
                  onAddParam={() => onAddParam(query.id)}
                  onDeleteParam={(paramId) => onDeleteParam(query.id, paramId)}
                  extractParamsFromSql={extractParamsFromSql}
                />
              ))}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </>
  )
}
