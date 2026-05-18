import type { TimeSeriesPoint } from "@/lib/types"

/** Порог разрыва на графике: если между точками больше N секунд — вставляем null. */
export const CHART_GAP_THRESHOLD_SECONDS = 3

export type ChartRow = Record<string, unknown> & { elapsedSeconds: number }

/** timeline — общая шкала прогона; overlay — каждая СУБД с t=0 от своего старта нагрузки. */
export type ChartTimelineMode = "timeline" | "overlay"

export const CHART_TIMELINE_MODE_LABELS: Record<ChartTimelineMode, string> = {
  timeline: "Хронология прогона",
  overlay: "Сравнение с нуля",
}

export const CHART_TIMELINE_AXIS_TITLE: Record<ChartTimelineMode, string> = {
  timeline: "Время от старта прогона (с)",
  overlay: "Время от старта нагрузки БД (с)",
}

function sortSeriesByTimestamp(
  realtimeData: Record<string, TimeSeriesPoint[]>,
): Record<string, TimeSeriesPoint[]> {
  const sorted: Record<string, TimeSeriesPoint[]> = {}
  for (const [dbId, pts] of Object.entries(realtimeData)) {
    if (!pts.length) continue
    sorted[dbId] = [...pts].sort((a, b) => a.timestamp - b.timestamp)
  }
  return sorted
}

/**
 * Преобразовать realtime/history точки в строки для Plotly.
 * timeline: общий anchor (первая точка среди всех серий) — последовательный прогон.
 * overlay: anchor на первую точку каждой серии — наложение для сравнения.
 */
export function buildChartDataFromTimeSeries(
  realtimeData: Record<string, TimeSeriesPoint[]>,
  options?: {
    gapThresholdSeconds?: number
    mode?: ChartTimelineMode
  },
): ChartRow[] {
  const gapThreshold = options?.gapThresholdSeconds ?? CHART_GAP_THRESHOLD_SECONDS
  const mode = options?.mode ?? "timeline"

  const sortedSeries = sortSeriesByTimestamp(realtimeData)
  const allPoints: Array<{ dbId: string; point: TimeSeriesPoint }> = []
  for (const [dbId, pts] of Object.entries(sortedSeries)) {
    for (const point of pts) {
      allPoints.push({ dbId, point })
    }
  }
  if (!allPoints.length) {
    return []
  }

  const globalAnchorTs = Math.min(...allPoints.map((item) => item.point.timestamp))
  const anchorByDb: Record<string, number> = {}
  for (const [dbId, pts] of Object.entries(sortedSeries)) {
    anchorByDb[dbId] = pts[0].timestamp
  }

  const rows: ChartRow[] = []
  const lastElapsedByDb: Record<string, number> = {}
  const insertGapRows = mode === "timeline"

  for (const { dbId, point } of allPoints.sort((a, b) => a.point.timestamp - b.point.timestamp)) {
    const anchorTs = mode === "overlay" ? anchorByDb[dbId] : globalAnchorTs
    const elapsedSeconds = Math.max(0, (point.timestamp - anchorTs) / 1000)
    const prevElapsed = lastElapsedByDb[dbId]
    if (
      insertGapRows
      && prevElapsed !== undefined
      && elapsedSeconds - prevElapsed > gapThreshold
    ) {
      const gapRow: ChartRow = { elapsedSeconds: prevElapsed + gapThreshold / 2 }
      gapRow[`${dbId}_responseTime`] = null
      gapRow[`${dbId}_throughput`] = null
      gapRow[`${dbId}_tps`] = null
      gapRow[`${dbId}_cpu`] = null
      gapRow[`${dbId}_memory`] = null
      gapRow[`${dbId}_diskIO`] = null
      gapRow[`${dbId}_connections`] = null
      gapRow[`${dbId}_errors`] = null
      rows.push(gapRow)
    }

    // Десятые доли секунды: в overlay не схлопывать две точки в одну секунду (редкий realtime).
    const rounded = Math.round(elapsedSeconds * 10) / 10
    let row = rows.find((r) => r.elapsedSeconds === rounded)
    if (!row) {
      row = { elapsedSeconds: rounded }
      rows.push(row)
    }

    row[`${dbId}_responseTime`] = point.responseTime ?? 0
    row[`${dbId}_throughput`] = point.throughput ?? 0
    row[`${dbId}_tps`] = point.tps ?? 0
    row[`${dbId}_cpu`] = point.cpuUsage ?? 0
    row[`${dbId}_memory`] = point.memoryUsage ?? 0
    row[`${dbId}_diskIO`] = point.diskIOps ?? 0
    row[`${dbId}_connections`] = point.activeConnections ?? 0
    row[`${dbId}_errors`] = point.errorCount ?? 0

    lastElapsedByDb[dbId] = elapsedSeconds
  }

  return rows.sort((a, b) => Number(a.elapsedSeconds) - Number(b.elapsedSeconds))
}

/**
 * Точки одной серии для Plotly: только свои X/Y, без null из-за других СУБД в общей таблице.
 */
export function extractDatabaseTrace(
  rows: ChartRow[],
  dbId: string,
  metricKey: string,
): { x: number[]; y: number[] } {
  const field = `${dbId}_${metricKey}`
  const x: number[] = []
  const y: number[] = []

  for (const row of rows) {
    const value = row[field]
    if (typeof value === "number") {
      x.push(Number(row.elapsedSeconds))
      y.push(value)
    }
  }

  return { x, y }
}

/** Подписи оси X (секунды): при коротком диапазоне — доли секунды, иначе целые. */
export function resolveElapsedAxisTickFormat(spanSeconds: number): {
  tickformat: string
  dtick?: number
  hoverFractionDigits: number
} {
  if (spanSeconds < 2) {
    return {
      tickformat: ".2f",
      dtick: spanSeconds <= 0.6 ? 0.1 : 0.2,
      hoverFractionDigits: 2,
    }
  }
  if (spanSeconds < 30) {
    return {
      tickformat: ".1f",
      hoverFractionDigits: 1,
    }
  }
  return {
    tickformat: ",d",
    hoverFractionDigits: 0,
  }
}

export function computeElapsedSpanSeconds(
  rows: ChartRow[],
  databases: string[],
  metricKey: string,
): number {
  let min = Infinity
  let max = -Infinity
  for (const dbId of databases) {
    const { x } = extractDatabaseTrace(rows, dbId, metricKey)
    for (const value of x) {
      if (value < min) min = value
      if (value > max) max = value
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return 0
  }
  return Math.max(0, max - min)
}
