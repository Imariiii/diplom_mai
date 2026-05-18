import { describe, expect, it } from "vitest"
import {
  buildChartDataFromTimeSeries,
  extractDatabaseTrace,
  resolveElapsedAxisTickFormat,
} from "@/lib/time-series-chart-data"
import type { TimeSeriesPoint } from "@/lib/types"

function makePoint(timestamp: number, responseTime = 10): TimeSeriesPoint {
  return {
    timestamp,
    responseTime,
    throughput: 1,
    tps: 1,
    activeConnections: 1,
    errorCount: 0,
    cpuUsage: 0,
    memoryUsage: 0,
    memoryUsageMB: 0,
    diskIOps: 0,
    networkIn: 0,
    networkOut: 0,
    cacheHitRatio: 0,
    bufferPoolHitRatio: 0,
    lockWaits: 0,
    deadlocks: 0,
  }
}

describe("buildChartDataFromTimeSeries", () => {
  it("uses a shared anchor across databases", () => {
    const rows = buildChartDataFromTimeSeries({
      dbA: [makePoint(1000)],
      dbB: [makePoint(5000)],
    })

    expect(rows.length).toBeGreaterThanOrEqual(2)
    const dbBRow = rows.find((row) => row.dbB_responseTime === 10)
    expect(dbBRow?.elapsedSeconds).toBe(4)
  })

  it("inserts null gap row when interval exceeds threshold in timeline mode", () => {
    const rows = buildChartDataFromTimeSeries({
      dbA: [makePoint(0), makePoint(10000)],
    }, { gapThresholdSeconds: 3, mode: "timeline" })

    const gapRow = rows.find((row) => row.dbA_responseTime === null)
    expect(gapRow).toBeDefined()
  })

  it("does not insert gap rows in overlay mode", () => {
    const rows = buildChartDataFromTimeSeries({
      dbA: [makePoint(0), makePoint(10000)],
    }, { gapThresholdSeconds: 3, mode: "overlay" })

    expect(rows.some((row) => row.dbA_responseTime === null)).toBe(false)
  })

  it("extractDatabaseTrace skips rows without values for the database", () => {
    const rows = buildChartDataFromTimeSeries(
      {
        dbA: [makePoint(0), makePoint(1000)],
        dbB: [makePoint(5000), makePoint(6000)],
      },
      { mode: "overlay" },
    )

    const traceA = extractDatabaseTrace(rows, "dbA", "responseTime")
    const traceB = extractDatabaseTrace(rows, "dbB", "responseTime")

    expect(traceA.x).toEqual([0, 1])
    expect(traceB.x).toEqual([0, 1])
    expect(traceA.y).toHaveLength(2)
    expect(traceB.y).toHaveLength(2)
  })

  it("overlay keeps sub-second points separate (sparse realtime)", () => {
    const rows = buildChartDataFromTimeSeries(
      {
        dbA: [makePoint(0), makePoint(280)],
      },
      { mode: "overlay" },
    )

    const trace = extractDatabaseTrace(rows, "dbA", "responseTime")
    expect(trace.x).toEqual([0, 0.3])
    expect(trace.y).toHaveLength(2)
  })

  it("overlay mode aligns each database from its own zero", () => {
    const rows = buildChartDataFromTimeSeries(
      {
        dbA: [makePoint(0), makePoint(5000)],
        dbB: [makePoint(30000), makePoint(35000)],
      },
      { mode: "overlay" },
    )

    const dbARow = rows.find((row) => row.dbA_responseTime === 10)
    const dbBRow = rows.find((row) => row.dbB_responseTime === 10)
    expect(dbARow?.elapsedSeconds).toBe(0)
    expect(dbBRow?.elapsedSeconds).toBe(0)
  })

  it("uses fractional tick format for sub-2s spans", () => {
    expect(resolveElapsedAxisTickFormat(0.3).tickformat).toBe(".2f")
    expect(resolveElapsedAxisTickFormat(0.3).dtick).toBe(0.1)
    expect(resolveElapsedAxisTickFormat(15).tickformat).toBe(".1f")
    expect(resolveElapsedAxisTickFormat(60).tickformat).toBe(",d")
  })

  it("timeline mode keeps later database offset on global axis", () => {
    const rows = buildChartDataFromTimeSeries(
      {
        dbA: [makePoint(0), makePoint(5000)],
        dbB: [makePoint(30000), makePoint(35000)],
      },
      { mode: "timeline" },
    )

    const dbBStart = rows.find((row) => row.dbB_responseTime === 10)
    expect(dbBStart?.elapsedSeconds).toBe(30)
  })
})
