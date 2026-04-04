"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CHART_COLORS } from "@/lib/chart-colors"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from "recharts"

interface TimeSeriesChartProps {
  title: string
  icon: React.ReactNode
  data: Record<string, unknown>[]
  databases: string[]
  dbNames: Record<string, string>
  getDbColor: (dbId: string) => string
  metricKey: string
  chartType?: "line" | "area"
  yDomain?: [number, number]
  customDbNames?: Record<string, string>
  getDbType?: (dbKey: string) => string
}

export function TimeSeriesChart({
  title,
  icon,
  data,
  databases,
  dbNames,
  getDbColor,
  metricKey,
  chartType = "line",
  yDomain,
  customDbNames,
  getDbType,
}: TimeSeriesChartProps) {
  const ChartComponent = chartType === "area" ? AreaChart : LineChart
  const SeriesComponent = chartType === "area" ? Area : Line

  const getDisplayName = (dbId: string) => {
    return customDbNames?.[dbId] || dbNames[dbId] || dbId
  }

  const resolveDbColor = (dbId: string) => {
    if (getDbType) {
      return getDbColor(getDbType(dbId))
    }
    return getDbColor(dbId)
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-foreground">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <ChartComponent data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="time"
                stroke={CHART_COLORS.axis}
                fontSize={12}
                tick={{ fill: CHART_COLORS.text }}
              />
              <YAxis
                stroke={CHART_COLORS.axis}
                fontSize={12}
                domain={yDomain}
                tick={{ fill: CHART_COLORS.text }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  color: CHART_COLORS.text,
                }}
                labelStyle={{ color: CHART_COLORS.text }}
                itemStyle={{ color: CHART_COLORS.text }}
              />
              <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
              {databases.map((dbId) => (
                <SeriesComponent
                  key={dbId}
                  type="monotone"
                  dataKey={`${dbId}_${metricKey}`}
                  name={getDisplayName(dbId)}
                  stroke={resolveDbColor(dbId)}
                  fill={chartType === "area" ? resolveDbColor(dbId) : undefined}
                  fillOpacity={chartType === "area" ? 0.2 : undefined}
                  strokeWidth={chartType === "line" ? 2 : undefined}
                  dot={chartType === "line" ? false : undefined}
                />
              ))}
            </ChartComponent>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
