"use client"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import type { Scenario } from "@/lib/types"

const SCENARIO_TYPES = [
  { value: "read_only", label: "Только чтение (100% SELECT)" },
  { value: "write_only", label: "Только запись" },
  { value: "mixed_light", label: "Смешанная лёгкая" },
  { value: "mixed_heavy", label: "Смешанная тяжёлая" },
  { value: "oltp", label: "OLTP" },
  { value: "olap", label: "OLAP" },
  { value: "custom", label: "Пользовательский" },
]

interface ScenarioListPanelProps {
  scenarios: Scenario[]
  selectedScenario: Scenario | null
  onSelect: (scenario: Scenario) => void
}

function getScenarioTypeLabel(type: string) {
  return SCENARIO_TYPES.find(t => t.value === type)?.label || type
}

export function ScenarioListPanel({ scenarios, selectedScenario, onSelect }: ScenarioListPanelProps) {
  return (
    <ScrollArea className="h-[500px]">
      <div className="space-y-2">
        {scenarios.map((scenario) => (
          <div
            key={scenario.id}
            onClick={() => onSelect(scenario)}
            className={`p-3 rounded-lg cursor-pointer transition-colors ${
              selectedScenario?.id === scenario.id
                ? "bg-primary/10 border border-primary/20"
                : "hover:bg-muted"
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{scenario.name}</span>
                  {scenario.is_builtin === 't' && (
                    <Badge variant="secondary" className="text-xs">built-in</Badge>
                  )}
                  {scenario.target_connection_id && (
                    <Badge variant="outline" className="text-xs">auto</Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {getScenarioTypeLabel(scenario.scenario_type)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}
