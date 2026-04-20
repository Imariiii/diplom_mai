"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Layers, Code } from "lucide-react"
import type { TestMode } from "@/lib/types"

interface TestModeSelectorCardProps {
  testMode: TestMode
  onModeChange: (mode: TestMode) => void
}

const testModes: { id: TestMode; name: string; description: string; icon: React.ElementType }[] = [
  {
    id: "scenario",
    name: "По сценарию",
    description: "Выбор предустановленного сценария нагрузки",
    icon: Layers,
  },
  {
    id: "custom_query",
    name: "Конкретный запрос",
    description: "Ввод произвольного SQL-запроса для тестирования",
    icon: Code,
  },
]

export function TestModeSelectorCard({ testMode, onModeChange }: TestModeSelectorCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-5 w-5 text-primary" />
          Режим тестирования
        </CardTitle>
        <CardDescription>Выберите способ проведения нагрузочного теста</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {testModes.map((mode) => {
            const Icon = mode.icon
            const isSelected = testMode === mode.id
            return (
              <label
                key={mode.id}
                className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  isSelected
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <input
                  type="radio"
                  name="testMode"
                  checked={isSelected}
                  onChange={() => onModeChange(mode.id)}
                  className="mt-1"
                />
                <div>
                  <div className="flex items-center gap-2 font-medium">
                    <Icon className="h-4 w-4" />
                    {mode.name}
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">
                    {mode.description}
                  </div>
                </div>
              </label>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
