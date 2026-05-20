import { describe, expect, it } from "vitest"
import {
  formatAttemptRateLabel,
  formatCardAttemptRate,
  formatCardSuccessfulThroughput,
  formatPrimaryThroughputLabel,
  formatSummaryUnitsLabel,
  formatWorkloadModeLabel,
  resolvePrimaryRateUnit,
  resolveWorkloadMode,
} from "./throughput-metrics"

describe("formatCardAttemptRate", () => {
  it("shows live attempt rate while test is running", () => {
    expect(
      formatCardAttemptRate({
        isTestFinished: false,
        attemptRate: 793,
        liveAttemptRate: "821.35",
      }),
    ).toBe("821.35")
  })

  it("shows final attempt rate when test finished, not throughput", () => {
    expect(
      formatCardAttemptRate({
        isTestFinished: true,
        attemptRate: 821,
        liveAttemptRate: "821.35",
      }),
    ).toBe("821")
  })

  it("shows dash when finished without attempt rate", () => {
    expect(
      formatCardAttemptRate({
        isTestFinished: true,
        liveAttemptRate: "—",
      }),
    ).toBe("—")
  })

  it("does not substitute successful throughput into attempt rate card", () => {
    expect(
      formatCardAttemptRate({
        isTestFinished: true,
        attemptRate: 821,
        liveAttemptRate: "793.00",
      }),
    ).not.toBe("793")
  })
})

describe("formatCardSuccessfulThroughput", () => {
  it("formats successful throughput as integer when finished", () => {
    expect(
      formatCardSuccessfulThroughput({
        isTestFinished: true,
        throughput: 793,
        liveThroughput: "800",
      }),
    ).toBe("793")
  })

  it("shows live throughput while running", () => {
    expect(
      formatCardSuccessfulThroughput({
        isTestFinished: false,
        liveThroughput: "812.5",
      }),
    ).toBe("812.5")
  })

  it("shows dash when throughput missing", () => {
    expect(
      formatCardSuccessfulThroughput({
        isTestFinished: true,
      }),
    ).toBe("—")
  })
})

describe("workload mode labels", () => {
  it("resolves workload mode with query default", () => {
    expect(resolveWorkloadMode(undefined)).toBe("query")
    expect(resolveWorkloadMode("transaction")).toBe("transaction")
  })

  it("formats bundle and throughput labels", () => {
    expect(formatWorkloadModeLabel("query")).toBe("SQL bundle")
    expect(formatWorkloadModeLabel("transaction")).toBe("Транзакционный bundle")
    expect(resolvePrimaryRateUnit("query")).toBe("qps")
    expect(resolvePrimaryRateUnit("transaction")).toBe("tps")
    expect(formatAttemptRateLabel("query")).toBe("Запросов/с")
    expect(formatPrimaryThroughputLabel("query")).toBe("Успешных запросов/с")
    expect(formatAttemptRateLabel("transaction")).toBe("Транзакций/с")
    expect(formatPrimaryThroughputLabel("transaction")).toBe("Успешных транзакций/с")
    expect(formatSummaryUnitsLabel("transaction")).toContain("транзакции")
  })
})
