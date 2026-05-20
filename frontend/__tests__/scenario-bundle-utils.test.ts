import { describe, expect, it } from "vitest"

import { buildScenarioBundleConfigPatch } from "@/lib/scenario-bundle-utils"
import type { ScenarioBundleSummary } from "@/lib/types"

function makeBundle(overrides: Partial<ScenarioBundleSummary>): ScenarioBundleSummary {
  return {
    id: "bundle-1",
    schema_profile_id: "profile-1",
    scenario_template_id: "scenario-1",
    name: "Bundle",
    generation_source: "manual",
    is_builtin: false,
    is_active: true,
    queries: [],
    indexes: [],
    ...overrides,
  }
}

describe("buildScenarioBundleConfigPatch", () => {
  it("preserves transaction workload metadata for live dashboards", () => {
    expect(buildScenarioBundleConfigPatch(makeBundle({
      workload_mode: "transaction",
      primary_rate_unit: "tps",
    }))).toEqual({
      bundleId: "bundle-1",
      workload_mode: "transaction",
      primary_rate_unit: "tps",
      comparison_unit: "transaction",
    })
  })
})
