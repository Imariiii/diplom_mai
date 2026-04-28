import { describe, expect, it } from "vitest"

import { getVisibleSelfCheckWarnings } from "@/lib/self-check"

describe("getVisibleSelfCheckWarnings", () => {
  it("hides old Little's law warnings when SQL concurrency is below virtual users", () => {
    const warnings = getVisibleSelfCheckWarnings({
      warnings: ["Закон Литтла нарушен: вычислено N=9.23, ожидалось 15"],
      littles_law: {
        reason: "concurrency_mismatch",
        computed_concurrency: 9.23,
        expected_concurrency: 15,
      },
    })

    expect(warnings).toEqual([])
  })

  it("keeps other warnings", () => {
    const warnings = getVisibleSelfCheckWarnings({
      warnings: ["Неконсистентный error_rate: actual=1.0000, expected=0.0000"],
      littles_law: {
        reason: null,
        computed_concurrency: 10,
        expected_concurrency: 10,
      },
    })

    expect(warnings).toEqual(["Неконсистентный error_rate: actual=1.0000, expected=0.0000"])
  })

  it("keeps Little's law warnings when SQL concurrency exceeds virtual users", () => {
    const warning = "Закон Литтла нарушен: вычислено N=18.50, ожидалось 10"
    const warnings = getVisibleSelfCheckWarnings({
      warnings: [warning],
      littles_law: {
        reason: "concurrency_mismatch",
        computed_concurrency: 18.5,
        expected_concurrency: 10,
      },
    })

    expect(warnings).toEqual([warning])
  })
})
