"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"

interface AddIndexDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tableName: string
  onTableNameChange: (value: string) => void
  columnNames: string
  onColumnNamesChange: (value: string) => void
  indexType: string
  onIndexTypeChange: (value: string) => void
  indexName: string
  onIndexNameChange: (value: string) => void
  description: string
  onDescriptionChange: (value: string) => void
  condition: string
  onConditionChange: (value: string) => void
  isUnique: boolean
  onIsUniqueChange: (value: boolean) => void
  onSubmit: () => void
}

const INDEX_TYPES = [
  { value: "btree", label: "BTREE" },
  { value: "hash", label: "HASH" },
  { value: "gin", label: "GIN (PostgreSQL)" },
  { value: "gist", label: "GIST (PostgreSQL)" },
]

export function AddIndexDialog({
  open,
  onOpenChange,
  tableName,
  onTableNameChange,
  columnNames,
  onColumnNamesChange,
  indexType,
  onIndexTypeChange,
  indexName,
  onIndexNameChange,
  description,
  onDescriptionChange,
  condition,
  onConditionChange,
  isUnique,
  onIsUniqueChange,
  onSubmit,
}: AddIndexDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Добавить индекс</DialogTitle>
          <DialogDescription>
            Индексы создаются перед запуском сценария и удаляются после завершения теста.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="index-table-name">Таблица</Label>
              <Input
                id="index-table-name"
                value={tableName}
                onChange={(e) => onTableNameChange(e.target.value)}
                placeholder="payment"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="index-columns">Колонки</Label>
              <Input
                id="index-columns"
                value={columnNames}
                onChange={(e) => onColumnNamesChange(e.target.value)}
                placeholder="rental_id, amount"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="index-type">Тип индекса</Label>
              <Select value={indexType} onValueChange={onIndexTypeChange}>
                <SelectTrigger id="index-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INDEX_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="index-name">Имя индекса (опционально)</Label>
              <Input
                id="index-name"
                value={indexName}
                onChange={(e) => onIndexNameChange(e.target.value)}
                placeholder="idx_loadtest_payment_rental_id_amount"
              />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <div className="space-y-1">
              <Label htmlFor="index-unique">Уникальный индекс</Label>
              <p className="text-xs text-muted-foreground">
                Используйте только если это соответствует данным и ограничениям схемы.
              </p>
            </div>
            <Switch
              id="index-unique"
              checked={isUnique}
              onCheckedChange={onIsUniqueChange}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="index-condition">Условие WHERE (опционально)</Label>
            <Input
              id="index-condition"
              value={condition}
              onChange={(e) => onConditionChange(e.target.value)}
              placeholder="amount > 0"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="index-description">Описание (опционально)</Label>
            <Textarea
              id="index-description"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder="Для ускорения JOIN и фильтрации"
              rows={3}
            />
          </div>
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
