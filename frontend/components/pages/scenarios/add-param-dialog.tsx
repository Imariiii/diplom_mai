"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

const PARAM_TYPES = [
  { value: "random_int", label: "Случайное целое число", hasMinMax: true },
  { value: "random_from_table", label: "Случайное значение из таблицы", hasTableRef: true },
  { value: "sequential_int", label: "Последовательное целое", hasMinMax: false },
  { value: "uuid", label: "UUID", hasMinMax: false },
  { value: "fixed", label: "Фиксированное значение", hasFixedValue: true },
  { value: "random_string", label: "Случайная строка", hasStringLength: true },
  { value: "random_date", label: "Случайная дата", hasMinMax: false },
]

interface AddParamDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  paramName: string
  onParamNameChange: (value: string) => void
  paramType: string
  onParamTypeChange: (value: string) => void
  minValue: number
  onMinValueChange: (value: number) => void
  maxValue: number
  onMaxValueChange: (value: number) => void
  tableRef: string
  onTableRefChange: (value: string) => void
  columnRef: string
  onColumnRefChange: (value: string) => void
  fixedValue: string
  onFixedValueChange: (value: string) => void
  stringLength: number
  onStringLengthChange: (value: number) => void
  onSubmit: () => void
}

export function AddParamDialog({
  open,
  onOpenChange,
  paramName,
  onParamNameChange,
  paramType,
  onParamTypeChange,
  minValue,
  onMinValueChange,
  maxValue,
  onMaxValueChange,
  tableRef,
  onTableRefChange,
  columnRef,
  onColumnRefChange,
  fixedValue,
  onFixedValueChange,
  stringLength,
  onStringLengthChange,
  onSubmit,
}: AddParamDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Добавить параметр</DialogTitle>
          <DialogDescription>
            Настройте генерацию значений для параметра SQL-запроса
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="param-name">Имя параметра</Label>
            <Input
              id="param-name"
              value={paramName}
              onChange={(e) => onParamNameChange(e.target.value)}
              placeholder="film_id"
            />
            <p className="text-xs text-muted-foreground">
              Должно совпадать с именем в SQL шаблоне (без фигурных скобок)
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="param-type">Тип генератора</Label>
            <Select value={paramType} onValueChange={onParamTypeChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PARAM_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {paramType === 'random_int' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Минимум</Label>
                <Input
                  type="number"
                  value={minValue}
                  onChange={(e) => onMinValueChange(parseInt(e.target.value) || 0)}
                />
              </div>
              <div className="space-y-2">
                <Label>Максимум</Label>
                <Input
                  type="number"
                  value={maxValue}
                  onChange={(e) => onMaxValueChange(parseInt(e.target.value) || 1000)}
                />
              </div>
            </div>
          )}

          {paramType === 'random_from_table' && (
            <>
              <div className="space-y-2">
                <Label>Таблица</Label>
                <Input
                  value={tableRef}
                  onChange={(e) => onTableRefChange(e.target.value)}
                  placeholder="film"
                />
              </div>
              <div className="space-y-2">
                <Label>Колонка</Label>
                <Input
                  value={columnRef}
                  onChange={(e) => onColumnRefChange(e.target.value)}
                  placeholder="film_id"
                />
              </div>
            </>
          )}

          {paramType === 'fixed' && (
            <div className="space-y-2">
              <Label>Фиксированное значение</Label>
              <Input
                value={fixedValue}
                onChange={(e) => onFixedValueChange(e.target.value)}
                placeholder="Значение"
              />
            </div>
          )}

          {paramType === 'random_string' && (
            <div className="space-y-2">
              <Label>Длина строки</Label>
              <Input
                type="number"
                value={stringLength}
                onChange={(e) => onStringLengthChange(parseInt(e.target.value) || 10)}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={onSubmit}>Добавить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
