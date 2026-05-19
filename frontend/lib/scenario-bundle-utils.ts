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
