import { describe, expect, it } from "vitest"
import {
  formatDbmsBufferSize,
  getBufferSizeLabel,
  getCacheHitDisplay,
  mapRawDbmsCacheFields,
} from "./dbms-cache-metrics"

describe("dbms-cache-metrics hybrid", () => {
  it("shows percent when display status ok", () => {
    const d = getCacheHitDisplay({ cacheHitRatio: 98.2, cacheHitRatioStatus: "ok" })
    expect(d.valueText).toBe("98.2%")
  })

  it("shows Н/Д with raw details when not meaningful", () => {
    const mapped = mapRawDbmsCacheFields({
      cache_hit_ratio: null,
      cache_hit_ratio_status: "no_activity",
      cache_hit_ratio_raw: 99.5,
      cache_hit_ratio_raw_status: "ok",
      cache_hit_ratio_meaningfulness: "not_meaningful_for_workload",
      cache_hit_ratio_scope: "engine_global",
    })
    const d = getCacheHitDisplay(mapped)
    expect(d.valueText).toBe("Н/Д")
    expect(d.details).toContain("Raw engine-level")
  })

  it("formats dbms-specific buffer size labels", () => {
    expect(getBufferSizeLabel("postgresql")).toBe("shared_buffers")
    expect(getBufferSizeLabel("mysql")).toBe("InnoDB buffer pool")
    expect(getBufferSizeLabel("mariadb")).toBe("InnoDB buffer pool")
    expect(formatDbmsBufferSize(1536)).toBe("1.50 GB")
  })
})
