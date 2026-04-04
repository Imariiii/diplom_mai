"use client"

import { Cpu, HardDrive, Zap } from "lucide-react"
import { DB_NAMES, getDbColor } from "@/lib/chart-colors"
import { TimeSeriesChart } from "./shared/time-series-chart"

interface SystemMetricsTabProps {
  databases: string[]
  chartData: Record<string, unknown>[]
  getDbType?: (dbKey: string) => string
  getDbDisplayName?: (dbKey: string) => string
}

export function SystemMetricsTab({ databases, chartData, getDbType, getDbDisplayName }: SystemMetricsTabProps) {
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
        />
        <TimeSeriesChart
          title="Disk I/O (ops/sec)"
          icon={<HardDrive className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="diskIO"
          chartType="area"
          customDbNames={customDbNames}
          getDbType={getDbType}
        />
        <TimeSeriesChart
          title="Пропускная способность (req/s)"
          icon={<Zap className="h-5 w-5 text-primary" />}
          data={chartData}
          databases={databases}
          dbNames={DB_NAMES}
          getDbColor={resolveDbColor}
          metricKey="throughput"
          chartType="area"
          customDbNames={customDbNames}
          getDbType={getDbType}
        />
      </div>
    </div>
  )
}
