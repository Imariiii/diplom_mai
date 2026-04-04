"use client"

import { Cpu, HardDrive, Zap } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { TimeSeriesChart } from "./shared/time-series-chart"

interface SystemMetricsTabProps {
  databases: string[]
  chartData: Record<string, unknown>[]
}

export function SystemMetricsTab({ databases, chartData }: SystemMetricsTabProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TimeSeriesChart
          title="Загрузка CPU (%)"
          icon={<Cpu className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="cpu"
          chartType="line"
          yDomain={[0, 100]}
        />
        <TimeSeriesChart
          title="Использование RAM (%)"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="memory"
          chartType="line"
          yDomain={[0, 100]}
        />
        <TimeSeriesChart
          title="Disk I/O (ops/sec)"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="diskIO"
          chartType="area"
        />
        <TimeSeriesChart
          title="Пропускная способность (req/s)"
          icon={<Zap className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={getDbColor}
          metricKey="throughput"
          chartType="area"
        />
      </div>
    </div>
  )
}
