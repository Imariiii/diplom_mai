"use client"

import { useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { CHART_COLORS } from "@/lib/chart-colors"
import { Maximize2 } from "lucide-react"
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
  Brush,
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
  yDomain?: [number | string, number | string]
  customDbNames?: Record<string, string>
  getDbType?: (dbKey: string) => string
}

const tooltipStyle = {
  backgroundColor: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  color: CHART_COLORS.text,
}

function ChartContent({
  data,
  databases,
  metricKey,
  chartType,
  yDomain,
  getDisplayName,
  resolveDbColor,
  height,
  showBrush,
}: {
  data: Record<string, unknown>[]
  databases: string[]
  metricKey: string
  chartType: "line" | "area"
  yDomain?: [number | string, number | string]
  getDisplayName: (dbId: string) => string
  resolveDbColor: (dbId: string) => string
  height: number | string
  showBrush: boolean
}) {
  const resolvedDomain = yDomain || ["auto", "auto"]

  const commonXAxis = (
    <XAxis
      dataKey="time"
      stroke={CHART_COLORS.axis}
      fontSize={12}
      tick={{ fill: CHART_COLORS.text }}
      interval="preserveStartEnd"
    />
  )

  const formatValue = (v: number) => {
    if (v == null || isNaN(v)) return "0"
    if (Math.abs(v) >= 10000) return `${(v / 1000).toFixed(0)}k`
    if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`
    if (Math.abs(v) >= 100) return v.toFixed(0)
    if (Math.abs(v) >= 1) return v.toFixed(1)
    return v.toFixed(2)
  }

  const commonYAxis = (
    <YAxis
      stroke={CHART_COLORS.axis}
      fontSize={11}
      domain={resolvedDomain}
      allowDataOverflow={false}
      tick={{ fill: CHART_COLORS.text }}
      width={55}
      tickFormatter={formatValue}
      tickCount={6}
    />
  )

  const commonTooltip = (
    <Tooltip
      contentStyle={tooltipStyle}
      labelStyle={{ color: CHART_COLORS.text }}
      itemStyle={{ color: CHART_COLORS.text }}
      formatter={(value: number) => formatValue(value)}
    />
  )

  const brush = showBrush && data.length > 10 ? (
    <Brush
      dataKey="time"
      height={28}
      stroke="hsl(var(--primary))"
      fill="hsl(var(--muted))"
      tickFormatter={() => ""}
    />
  ) : null

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {chartType === "area" ? (
          <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            {commonXAxis}
            {commonYAxis}
            {commonTooltip}
            <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
            {databases.map((dbId) => (
              <Area
                key={dbId}
                type="monotone"
                dataKey={`${dbId}_${metricKey}`}
                name={getDisplayName(dbId)}
                stroke={resolveDbColor(dbId)}
                fill={resolveDbColor(dbId)}
                fillOpacity={0.2}
                connectNulls
              />
            ))}
            {brush}
          </AreaChart>
        ) : (
          <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            {commonXAxis}
            {commonYAxis}
            {commonTooltip}
            <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
            {databases.map((dbId) => (
              <Line
                key={dbId}
                type="monotone"
                dataKey={`${dbId}_${metricKey}`}
                name={getDisplayName(dbId)}
                stroke={resolveDbColor(dbId)}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
            {brush}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  )
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
  const [fullscreen, setFullscreen] = useState(false)

  const getDisplayName = useCallback(
    (dbId: string) => customDbNames?.[dbId] || dbNames[dbId] || dbId,
    [customDbNames, dbNames],
  )

  const resolveDbColor = useCallback(
    (dbId: string) => (getDbType ? getDbColor(getDbType(dbId)) : getDbColor(dbId)),
    [getDbType, getDbColor],
  )

  return (
    <>
      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-foreground">
              {icon}
              {title}
            </CardTitle>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={() => setFullscreen(true)}
              title="Развернуть"
            >
              <Maximize2 className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <ChartContent
            data={data}
            databases={databases}
            metricKey={metricKey}
            chartType={chartType}
            yDomain={yDomain}
            getDisplayName={getDisplayName}
            resolveDbColor={resolveDbColor}
            height={300}
            showBrush={false}
          />
        </CardContent>
      </Card>

      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-[calc(100vw-2rem)] w-[calc(100vw-2rem)] h-[calc(100vh-2rem)] max-h-[calc(100vh-2rem)] flex flex-col">
          <DialogHeader className="flex-shrink-0">
            <DialogTitle className="flex items-center gap-2">
              {icon}
              {title}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0">
            <ChartContent
              data={data}
              databases={databases}
              metricKey={metricKey}
              chartType={chartType}
              yDomain={yDomain}
              getDisplayName={getDisplayName}
              resolveDbColor={resolveDbColor}
              height="100%"
              showBrush={true}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
