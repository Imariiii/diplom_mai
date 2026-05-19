import { describe, expect, it } from "vitest"
import { findActiveScenarioBundle, isBundleActive } from "./scenario-bundle-utils"
import type { ScenarioBundleSummary } from "./types"

function bundle(partial: Partial<ScenarioBundleSummary>): ScenarioBundleSummary {
  return {
    id: "b1",
    schema_profile_id: "p1",
    scenario_template_id: "custom_transaction",
    name: "Transaction bundle 1",
    generation_source: "manual_variant",
    is_builtin: false,
    is_active: true,
    workload_mode: "transaction",
    queries: [],
    transactions: [],
    indexes: [],
    ...partial,
  }
}

describe("findActiveScenarioBundle", () => {
  it("finds active transaction bundle by template id", () => {
    const found = findActiveScenarioBundle(
      [
        bundle({ workload_mode: "transaction", is_active: true }),
        bundle({ id: "b2", scenario_template_id: "mixed_light", is_active: true }),
      ],
      "custom_transaction",
    )
    expect(found?.name).toBe("Transaction bundle 1")
  })

  it("ignores inactive bundle", () => {
    const found = findActiveScenarioBundle(
      [bundle({ is_active: false })],
      "custom_transaction",
    )
    expect(found).toBeUndefined()
  })
})

describe("isBundleActive", () => {
  it("accepts boolean and legacy string flags", () => {
    expect(isBundleActive(bundle({ is_active: true }))).toBe(true)
    expect(isBundleActive(bundle({ is_active: "t" as unknown as boolean }))).toBe(true)
    expect(isBundleActive(bundle({ is_active: false }))).toBe(false)
  })
})
