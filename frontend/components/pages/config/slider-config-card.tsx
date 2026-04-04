"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import type { LucideIcon } from "lucide-react"

interface SliderConfigCardProps {
  title: string
  icon: LucideIcon
  value: number
  min: number
  max: number
  step: number
  unit: string
  description: string
  presets?: number[]
  onValueChange: (value: number) => void
}

export function SliderConfigCard({
  title,
  icon: Icon,
  value,
  min,
  max,
  step,
  unit,
  description,
  presets,
  onValueChange,
}: SliderConfigCardProps) {
  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <CardDescription>{description}: {value}{unit}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Slider
          value={[value]}
          onValueChange={([v]) => onValueChange(v)}
          min={min}
          max={max}
          step={step}
          className="w-full"
        />
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{min}{unit}</span>
          <span>{Math.round((min + max) / 2)}{unit}</span>
          <span>{max}{unit}</span>
        </div>
        {presets && (
          <div className="grid grid-cols-4 gap-2">
            {presets.map((preset) => (
              <Button
                key={preset}
                variant={value === preset ? "default" : "outline"}
                size="sm"
                onClick={() => onValueChange(preset)}
              >
                {preset}
              </Button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
