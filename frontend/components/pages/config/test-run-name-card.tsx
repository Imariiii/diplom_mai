"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const MAX_NAME_LENGTH = 255

interface TestRunNameCardProps {
  value: string
  onChange: (value: string) => void
}

export function TestRunNameCard({ value, onChange }: TestRunNameCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle>Название прогона</CardTitle>
        <CardDescription>
          Отображается в истории и сравнении. Пустое поле — имя с датой и временем.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <Label htmlFor="test-run-display-name">Название</Label>
          <Input
            id="test-run-display-name"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            maxLength={MAX_NAME_LENGTH}
            placeholder="Например: Pagila · mixed_light · 10 VU"
            autoComplete="off"
          />
        </div>
      </CardContent>
    </Card>
  )
}
