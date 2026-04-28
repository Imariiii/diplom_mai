export interface SelfCheckPayload {
  warnings?: unknown
  littles_law?: {
    reason?: string | null
    computed_concurrency?: number | null
    computed_sql_concurrency?: number | null
    expected_concurrency?: number | null
  } | null
}

function isObsoleteLowSqlConcurrencyWarning(selfCheck: SelfCheckPayload, warning: string): boolean {
  const littlesLaw = selfCheck.littles_law
  if (!littlesLaw || littlesLaw.reason !== "concurrency_mismatch") {
    return false
  }

  const computed = littlesLaw.computed_sql_concurrency ?? littlesLaw.computed_concurrency
  const expected = littlesLaw.expected_concurrency
  if (typeof computed !== "number" || typeof expected !== "number") {
    return false
  }

  return warning.includes("Закон Литтла нарушен") && computed <= expected
}

export function getVisibleSelfCheckWarnings(selfCheck?: SelfCheckPayload | null): string[] {
  if (!selfCheck || !Array.isArray(selfCheck.warnings)) {
    return []
  }

  return selfCheck.warnings.filter((warning): warning is string => {
    return typeof warning === "string"
      && warning.length > 0
      && !isObsoleteLowSqlConcurrencyWarning(selfCheck, warning)
  })
}
