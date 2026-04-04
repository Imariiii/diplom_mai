"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface AddQueryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  queryType: "select" | "insert" | "update" | "delete"
  onQueryTypeChange: (value: "select" | "insert" | "update" | "delete") => void
  weight: number
  onWeightChange: (value: number) => void
  sql: string
  onSqlChange: (value: string) => void
  description: string
  onDescriptionChange: (value: string) => void
  onSubmit: () => void
}

export function AddQueryDialog({
  open,
  onOpenChange,
  queryType,
  onQueryTypeChange,
  weight,
  onWeightChange,
  sql,
  onSqlChange,
  description,
  onDescriptionChange,
  onSubmit,
}: AddQueryDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Добавить SQL-запрос</DialogTitle>
          <DialogDescription>
            Добавьте запрос с параметрами в формате {"{param_name}"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="query-type">Тип запроса</Label>
              <Select value={queryType} onValueChange={(v) => onQueryTypeChange(v as any)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="select">SELECT</SelectItem>
                  <SelectItem value="insert">INSERT</SelectItem>
                  <SelectItem value="update">UPDATE</SelectItem>
                  <SelectItem value="delete">DELETE</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="query-weight">Вес (приоритет)</Label>
              <Input
                id="query-weight"
                type="number"
                min={1}
                max={10}
                value={weight}
                onChange={(e) => onWeightChange(parseInt(e.target.value) || 1)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="query-sql">SQL шаблон</Label>
            <Textarea
              id="query-sql"
              value={sql}
              onChange={(e) => onSqlChange(e.target.value)}
              placeholder="SELECT * FROM film WHERE film_id = {film_id}"
              rows={4}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Используйте {"{parameter_name}"} для параметров, которые будут генерироваться автоматически
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="query-desc">Описание (опционально)</Label>
            <Input
              id="query-desc"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder="Описание запроса"
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
