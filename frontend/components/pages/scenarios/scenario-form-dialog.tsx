"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const SCENARIO_TYPES = [
  { value: "read_only", label: "Только чтение (100% SELECT)", description: "Чистые SELECT-запросы для проверки чтения" },
  { value: "write_only", label: "Только запись (100% INSERT/UPDATE/DELETE)", description: "Тестирование производительности записи" },
  { value: "mixed_light", label: "Смешанная нагрузка лёгкая (80% SELECT, 20% UPDATE)", description: "Похоже на реальный OLTP-режим" },
  { value: "mixed_heavy", label: "Смешанная нагрузка тяжёлая (50% SELECT, 50% UPDATE)", description: "Высокая нагрузка на запись" },
  { value: "oltp", label: "OLTP-подобная нагрузка", description: "Смесь коротких транзакций" },
  { value: "olap", label: "OLAP-подобная нагрузка", description: "Сложные аналитические запросы" },
  { value: "custom", label: "Пользовательский сценарий", description: "Полностью настраиваемый" },
]

interface ScenarioFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  mode: "create" | "edit"
  name: string
  onNameChange: (value: string) => void
  description: string
  onDescriptionChange: (value: string) => void
  scenarioType: string
  onScenarioTypeChange: (value: string) => void
  onSubmit: () => void
}

export function ScenarioFormDialog({
  open,
  onOpenChange,
  mode,
  name,
  onNameChange,
  description,
  onDescriptionChange,
  scenarioType,
  onScenarioTypeChange,
  onSubmit,
}: ScenarioFormDialogProps) {
  const isCreate = mode === "create"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isCreate ? "Создать сценарий" : "Редактировать сценарий"}</DialogTitle>
          {isCreate && (
            <DialogDescription>
              Создайте новый сценарий нагрузочного тестирования
            </DialogDescription>
          )}
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor={`${mode}-name`}>Название</Label>
            <Input
              id={`${mode}-name`}
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder={isCreate ? "Например: Интенсивное чтение фильмов" : undefined}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${mode}-type`}>Тип сценария</Label>
            <Select value={scenarioType} onValueChange={onScenarioTypeChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SCENARIO_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    <div className="flex flex-col items-start">
                      <span>{type.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {type.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${mode}-description`}>Описание</Label>
            <Textarea
              id={`${mode}-description`}
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder={isCreate ? "Опишите назначение сценария..." : undefined}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={onSubmit}>{isCreate ? "Создать" : "Сохранить"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
