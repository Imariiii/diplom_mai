"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Layers } from "lucide-react"
import type { TestMode } from "@/lib/types"

interface TestModeSelectorCardProps {
  testMode: TestMode
  onModeChange: (mode: TestMode) => void
}

const testModes: { id: TestMode; name: string; description: string }[] = [
  {
    id: "scenario",
    name: "По сценарию",
    description: "Предустановленный сценарий нагрузки",
  },
  {
    id: "custom_query",
    name: "Конкретный запрос",
    description: "Произвольный SQL для тестирования",
  },
]

/** Взаимоисключающий выбор без видимых радиокнопок — карточки как в блоке «Выбор базы данных» (radiogroup для доступности) */
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
        <div
          className="grid grid-cols-1 gap-3 sm:grid-cols-2"
          role="radiogroup"
          aria-label="Режим тестирования"
        >
          {testModes.map((mode) => {
            const isSelected = testMode === mode.id
            return (
              <button
                key={mode.id}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => onModeChange(mode.id)}
                className={`rounded-lg border p-4 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none ${
                  isSelected
                    ? "border-primary bg-primary/10"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <div className="font-medium text-sm">{mode.name}</div>
                <div className="mt-1 text-xs text-muted-foreground">{mode.description}</div>
              </button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
