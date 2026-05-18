import { describe, expect, it } from "vitest"
import {
  formatCardAttemptRate,
  formatCardSuccessfulThroughput,
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
  it("formats successful throughput as integer", () => {
    expect(formatCardSuccessfulThroughput(793)).toBe("793")
  })

  it("shows dash when throughput missing", () => {
    expect(formatCardSuccessfulThroughput(undefined)).toBe("—")
  })
})
