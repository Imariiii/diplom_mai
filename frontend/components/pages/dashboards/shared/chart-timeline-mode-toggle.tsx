"use client"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  CHART_TIMELINE_MODE_LABELS,
  type ChartTimelineMode,
} from "@/lib/time-series-chart-data"

interface ChartTimelineModeToggleProps {
  value: ChartTimelineMode
  onChange: (mode: ChartTimelineMode) => void
  disabled?: boolean
}

export function ChartTimelineModeToggle({
  value,
  onChange,
  disabled = false,
}: ChartTimelineModeToggleProps) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
      <p className="text-sm text-muted-foreground">
        {value === "overlay"
          ? "Все СУБД начинаются с 0 с — удобно сравнивать форму кривых нагрузки."
          : "Общая шкала прогона — видна последовательность нагрузки по СУБД."}
      </p>
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={value}
        onValueChange={(next) => {
          if (next === "timeline" || next === "overlay") {
            onChange(next)
          }
        }}
        disabled={disabled}
        className="shrink-0 bg-background"
      >
        <ToggleGroupItem value="timeline" aria-label={CHART_TIMELINE_MODE_LABELS.timeline}>
          {CHART_TIMELINE_MODE_LABELS.timeline}
        </ToggleGroupItem>
        <ToggleGroupItem value="overlay" aria-label={CHART_TIMELINE_MODE_LABELS.overlay}>
          {CHART_TIMELINE_MODE_LABELS.overlay}
        </ToggleGroupItem>
      </ToggleGroup>
    </div>
  )
}
