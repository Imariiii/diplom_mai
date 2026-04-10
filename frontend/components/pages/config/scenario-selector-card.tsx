"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Layers } from "lucide-react"
import type { Scenario } from "@/lib/types"

interface ScenarioSelectorCardProps {
  scenarios: Scenario[]
  selectedScenarioId: string | undefined
  useIndexes: boolean
  onScenarioChange: (id: string) => void
  onUseIndexesChange: (value: boolean) => void
}

export function ScenarioSelectorCard({
  scenarios,
  selectedScenarioId,
  useIndexes,
  onScenarioChange,
  onUseIndexesChange,
}: ScenarioSelectorCardProps) {
  const selectedScenario = scenarios?.find(s => s.id === selectedScenarioId)
  const indexesCount = selectedScenario?.indexes?.length ?? 0

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-primary" />
          Сценарий тестирования
        </CardTitle>
        <CardDescription>Выберите тип нагрузки для теста</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Select
          value={selectedScenarioId}
          onValueChange={(value) => onScenarioChange(value)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Выберите сценарий" />
          </SelectTrigger>
          <SelectContent>
            {(scenarios || []).map((scenario) => (
              <SelectItem key={scenario.id} value={scenario.id}>
                <div className="flex flex-col">
                  <span>{scenario.name}</span>
                  <span className="text-xs text-muted-foreground">{scenario.description}</span>
                </div>
              </SelectItem>
            ))}
            {(scenarios || []).length === 0 && (
              <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                Нет доступных сценариев
              </div>
            )}
          </SelectContent>
        </Select>

        {selectedScenario && (
          <div className="p-4 bg-muted rounded-lg space-y-4">
            <div className="space-y-2">
              <div className="font-medium">{selectedScenario.name || 'Без названия'}</div>
              <div className="text-sm text-muted-foreground">{selectedScenario.description || 'Нет описания'}</div>
            </div>
            <div className="flex gap-4 text-sm flex-wrap">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span>Запросов: {selectedScenario.queries_count ?? selectedScenario.queries?.length ?? 0}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                <span>Тип: {selectedScenario.scenario_type || 'custom'}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-amber-500 rounded-full"></div>
                <span>Индексов: {indexesCount}</span>
              </div>
              {selectedScenario.is_builtin && (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span>Системный</span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
              <div className="space-y-1">
                <Label htmlFor="use-indexes-switch" className="cursor-pointer">
                  Использовать индексы
                </Label>
                <p className="text-xs text-muted-foreground">
                  Индексы будут созданы до начала замеров и удалены после завершения теста
                </p>
              </div>
              <Switch
                id="use-indexes-switch"
                checked={useIndexes}
                disabled={indexesCount === 0}
                onCheckedChange={onUseIndexesChange}
              />
            </div>
            {indexesCount === 0 && (
              <p className="text-xs text-muted-foreground">
                Для выбранного сценария пока не настроены индексы.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
