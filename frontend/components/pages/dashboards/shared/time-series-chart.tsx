"use client"

import { useMemo, useState, useCallback } from "react"
import dynamic from "next/dynamic"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Maximize2 } from "lucide-react"
import type { ChartRow } from "@/lib/time-series-chart-data"
import {
  computeElapsedSpanSeconds,
  extractDatabaseTrace,
  resolveElapsedAxisTickFormat,
} from "@/lib/time-series-chart-data"
import { useChartTheme } from "@/lib/chart-theme"

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false }) as any

interface TimeSeriesChartProps {
  title: string
  description?: string
  icon: React.ReactNode
  data: ChartRow[]
  databases: string[]
  dbNames: Record<string, string>
  getDbColor: (dbId: string) => string
  metricKey: string
  chartType?: "line" | "area"
  yDomain?: [number | string, number | string]
  customDbNames?: Record<string, string>
  getDbType?: (dbKey: string) => string
  xAxisTitle?: string
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
  xAxisTitle = "Время от старта (с)",
}: {
  data: ChartRow[]
  databases: string[]
  metricKey: string
  chartType: "line" | "area"
  yDomain?: [number | string, number | string]
  getDisplayName: (dbId: string) => string
  resolveDbColor: (dbId: string) => string
  height: number | string
  xAxisTitle?: string
}) {
  const chartTheme = useChartTheme()

  const elapsedSpanSeconds = useMemo(
    () => computeElapsedSpanSeconds(data, databases, metricKey),
    [data, databases, metricKey],
  )

  const xAxisTicks = useMemo(
    () => resolveElapsedAxisTickFormat(elapsedSpanSeconds),
    [elapsedSpanSeconds],
  )

  const traces = useMemo(() => {
    const hoverTime = `%{x:.${xAxisTicks.hoverFractionDigits}f}`
    return databases.map((dbId) => {
      const { x, y } = extractDatabaseTrace(data, dbId, metricKey)
      return {
        type: "scattergl",
        mode: "lines+markers",
        name: getDisplayName(dbId),
        x,
        y,
        line: { color: resolveDbColor(dbId), width: 2 },
        marker: { color: resolveDbColor(dbId), size: 5 },
        connectgaps: false,
        fill: chartType === "area" ? "tozeroy" : "none",
        opacity: chartType === "area" ? 0.75 : 1,
        hovertemplate: `%{fullData.name}<br>t=${hoverTime}s<br>v=%{y:.2f}<extra></extra>`,
      }
    })
  }, [chartType, data, databases, getDisplayName, metricKey, resolveDbColor, xAxisTicks.hoverFractionDigits])

  const layout = useMemo(() => ({
    autosize: true,
    margin: { l: 55, r: 20, t: 12, b: 42 },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    hovermode: "closest",
    dragmode: "pan",
    font: { color: chartTheme.foreground, size: 11 },
    legend: {
      orientation: "h",
      y: -0.18,
      x: 0,
      font: { size: 11, color: chartTheme.mutedForeground },
    },
    xaxis: {
      title: { text: xAxisTitle, font: { color: chartTheme.mutedForeground, size: 11 } },
      tickmode: xAxisTicks.dtick !== undefined ? "linear" : "auto",
      dtick: xAxisTicks.dtick,
      gridcolor: chartTheme.border,
      zerolinecolor: chartTheme.border,
      tickformat: xAxisTicks.tickformat,
      tickprefix: "",
      ticksuffix: "s",
      tickfont: { size: 11, color: chartTheme.mutedForeground },
    },
    yaxis: {
      autorange: yDomain ? false : true,
      range: yDomain ? [yDomain[0], yDomain[1]] : undefined,
      gridcolor: chartTheme.border,
      zerolinecolor: chartTheme.border,
      tickfont: { size: 11, color: chartTheme.mutedForeground },
    },
  }), [
    chartTheme.border,
    chartTheme.foreground,
    chartTheme.mutedForeground,
    xAxisTicks.dtick,
    xAxisTicks.tickformat,
    xAxisTitle,
    yDomain,
  ])

  return (
    <div style={{ height }}>
      <Plot
        data={traces}
        layout={layout}
        style={{ width: "100%", height: "100%" }}
        config={{
          responsive: true,
          displaylogo: false,
          scrollZoom: true,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
        }}
      />
    </div>
  )
}

export function TimeSeriesChart({
  title,
  description,
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
  xAxisTitle,
}: TimeSeriesChartProps) {
  const [fullscreen, setFullscreen] = useState(false)

  const getDisplayName = useCallback(
    (dbId: string) => customDbNames?.[dbId] || dbNames[dbId] || dbId,
    [customDbNames, dbNames],
  )

  const resolveDbColor = useCallback(
    (dbId: string) => (getDbType ? getDbColor(getDbType(dbId)) : getDbColor(dbId)),
    [getDbColor, getDbType],
  )

  return (
    <>
      <Card className="bg-card border-border">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-foreground">
                {icon}
                {title}
              </CardTitle>
              {description && (
                <CardDescription className="mt-1">{description}</CardDescription>
              )}
            </div>
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
            height={320}
            xAxisTitle={xAxisTitle}
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
              xAxisTitle={xAxisTitle}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
