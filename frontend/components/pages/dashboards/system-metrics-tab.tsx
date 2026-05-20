"use client"

import { Cpu, HardDrive, Network } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import type { ChartRow, ChartTimelineMode } from "@/lib/time-series-chart-data"
import { ChartTimelineModeToggle } from "./shared/chart-timeline-mode-toggle"
import { TimeSeriesChart } from "./shared/time-series-chart"

interface SystemMetricsTabProps {
  databases: string[]
  chartData: ChartRow[]
  getDbType?: (dbKey: string) => string
  getDbDisplayName?: (dbKey: string) => string
  chartXAxisTitle?: string
  chartTimelineMode?: ChartTimelineMode
  onChartTimelineModeChange?: (mode: ChartTimelineMode) => void
}

export function SystemMetricsTab({ databases, chartData, getDbType, getDbDisplayName, chartXAxisTitle, chartTimelineMode, onChartTimelineModeChange }: SystemMetricsTabProps) {
  const resolveDbColor = (dbId: string) => {
    if (getDbType) {
      return getDbColor(getDbType(dbId))
    }
    return getDbColor(dbId)
  }

  const customDbNames = getDbDisplayName
    ? Object.fromEntries(databases.map((db) => [db, getDbDisplayName(db)]))
    : undefined

  return (
    <div className="space-y-6">
      {databases.length > 1 && chartTimelineMode && onChartTimelineModeChange && (
        <ChartTimelineModeToggle
          value={chartTimelineMode}
          onChange={onChartTimelineModeChange}
        />
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TimeSeriesChart
          title="Загрузка CPU (%)"
          icon={<Cpu className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="cpu"
          chartType="line"
          yDomain={[0, 100]}
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
        <TimeSeriesChart
          title="Использование RAM (%)"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="memory"
          chartType="line"
          yDomain={[0, 100]}
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
        <TimeSeriesChart
          title="Использование RAM (МБ)"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="memoryMB"
          chartType="line"
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
        <TimeSeriesChart
          title="Disk I/O (ops/s)"
          description="Скорость операций диска за интервал сэмпла"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="diskIO"
          chartType="area"
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
        <TimeSeriesChart
          title="Сеть: входящий (MiB/s)"
          icon={<Network className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="networkIn"
          chartType="area"
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
        <TimeSeriesChart
          title="Сеть: исходящий (MiB/s)"
          icon={<Network className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="networkOut"
          chartType="area"
          customDbNames={customDbNames}
          getDbType={getDbType}
          xAxisTitle={chartXAxisTitle}
        />
      </div>
    </div>
  )
}
