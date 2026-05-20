import type { ScenarioBundleSummary } from "@/lib/types"

/** Признак активного bundle (API отдаёт boolean, старые данные могли быть иначе). */
export function isBundleActive(bundle: ScenarioBundleSummary): boolean {
  const value = bundle.is_active as boolean | string | undefined
  return value === true || value === "t" || value === "T"
}

/** Найти активный bundle для выбранного logical template (query или transaction). */
export function findActiveScenarioBundle(
  bundles: ScenarioBundleSummary[],
  scenarioTemplateId: string | undefined,
): ScenarioBundleSummary | undefined {
  if (!scenarioTemplateId) return undefined
  return bundles.find(
    (bundle) => bundle.scenario_template_id === scenarioTemplateId && isBundleActive(bundle),
  )
}

export function buildScenarioBundleConfigPatch(bundle: ScenarioBundleSummary): {
  bundleId: string
  workload_mode: "query" | "transaction"
  primary_rate_unit: "qps" | "tps"
  comparison_unit: "query" | "transaction"
} {
  const workloadMode = bundle.workload_mode === "transaction" ? "transaction" : "query"
  return {
    bundleId: bundle.id,
    workload_mode: workloadMode,
    primary_rate_unit: bundle.primary_rate_unit === "tps" || bundle.primary_rate_unit === "qps"
      ? bundle.primary_rate_unit
      : workloadMode === "transaction" ? "tps" : "qps",
    comparison_unit: workloadMode === "transaction" ? "transaction" : "query",
  }
}
