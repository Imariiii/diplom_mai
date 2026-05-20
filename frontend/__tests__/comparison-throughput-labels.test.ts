import { describe, expect, it } from "vitest"
import {
  formatComparisonThroughputMeanLabel,
  formatComparisonThroughputRateUnit,
  formatComparisonThroughputTitle,
  formatComparisonThroughputValue,
  resolveComparisonWorkloadMode,
  resolveComparisonWorkloadModeFromTest,
} from "@/lib/throughput-metrics"

describe("comparison throughput labels", () => {
  it("uses query units for SQL workloads", () => {
    expect(formatComparisonThroughputRateUnit("query")).toBe("запросов/с")
    expect(formatComparisonThroughputTitle("query")).toBe("Пропускная способность (запросов/с)")
    expect(formatComparisonThroughputMeanLabel("query")).toBe(
      "Пропускная способность (среднее, запросов/с)",
    )
    expect(formatComparisonThroughputValue(812, "query")).toBe("812 запросов/с")
  })

  it("uses transaction units for transaction workloads", () => {
    expect(formatComparisonThroughputRateUnit("transaction")).toBe("транзакций/с")
    expect(formatComparisonThroughputTitle("transaction")).toBe(
      "Пропускная способность (транзакций/с)",
    )
    expect(formatComparisonThroughputMeanLabel("transaction")).toBe(
      "Пропускная способность (среднее, транзакций/с)",
    )
    expect(formatComparisonThroughputValue(578, "transaction")).toBe("578 транзакций/с")
  })

  it("resolves workload mode from comparison test info", () => {
    expect(
      resolveComparisonWorkloadModeFromTest({
        scenario_info: { workload_mode: "transaction" },
      }),
    ).toBe("transaction")
    expect(
      resolveComparisonWorkloadMode({
        analysis_mode: "per_test",
        test: { config: { workload_mode: "query" } },
      }),
    ).toBe("query")
    expect(
      resolveComparisonWorkloadMode({
        analysis_mode: "series",
        tests: [{ scenario_info: { workload_mode: "transaction" } }],
      }),
    ).toBe("transaction")
  })
})
