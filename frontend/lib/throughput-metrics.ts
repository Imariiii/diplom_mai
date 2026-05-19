/**
 * Нормализация метрик пропускной способности (обратная совместимость со старыми прогонами).
 *
 * throughput — успешных SQL-операций/с (итог прогона);
 * attempt_rate — всех запросов/с (realtime и итоговая интенсивность).
 */

export type ThroughputMetricsRaw = {
  throughput?: number | null
  tps?: number | null
  attempt_rate?: number | null
  attemptRate?: number | null
  completed_tps?: number | null
}

export function resolveAggregateThroughput(raw: ThroughputMetricsRaw): number {
  const value = raw.throughput ?? raw.tps
  return typeof value === "number" ? value : 0
}

export function resolveAggregateAttemptRate(
  raw: ThroughputMetricsRaw,
): number | undefined {
  const value = raw.attempt_rate ?? raw.attemptRate ?? raw.completed_tps
  return typeof value === "number" ? value : undefined
}

/** Значение запросов/с для точки временного ряда (live хранится в throughput или attempt_rate). */
export function timeSeriesAttemptRate(raw: {
  throughput?: number | null
  tps?: number | null
  attempt_rate?: number | null
}): number {
  const value = raw.attempt_rate ?? raw.throughput ?? raw.tps
  return typeof value === "number" ? value : 0
}

export function pickAggregateThroughput(
  stats: Record<string, unknown>,
): number | undefined {
  const value = stats.throughput ?? stats.tps
  return typeof value === "number" ? value : undefined
}

export function pickAggregateAttemptRate(
  stats: Record<string, unknown>,
): number | undefined {
  const value = stats.attempt_rate ?? stats.completed_tps
  return typeof value === "number" ? value : undefined
}

/** «Запросы/с» в карточке: live attempt_rate во время теста, итог attempt_rate после завершения. */
export function formatCardAttemptRate(options: {
  isTestFinished: boolean
  attemptRate?: number
  liveAttemptRate: string
}): string {
  const { isTestFinished, attemptRate, liveAttemptRate } = options
  if (isTestFinished) {
    return typeof attemptRate === "number" ? attemptRate.toFixed(0) : "—"
  }
  return liveAttemptRate.trim() !== "" ? liveAttemptRate : "—"
}

/** «Успешных запросов/с» в карточке — только итоговый throughput после завершения теста. */
export function formatCardSuccessfulThroughput(throughput?: number): string {
  return typeof throughput === "number" ? throughput.toFixed(0) : "—"
}

export type WorkloadMode = "query" | "transaction"

export function resolveWorkloadMode(
  value?: string | null,
): WorkloadMode {
  return value === "transaction" ? "transaction" : "query"
}

export function resolvePrimaryRateUnit(
  workloadMode: WorkloadMode,
  explicit?: string | null,
): "qps" | "tps" {
  if (explicit === "tps" || explicit === "qps") return explicit
  return workloadMode === "transaction" ? "tps" : "qps"
}

export function formatWorkloadModeLabel(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Транзакционный bundle"
    : "SQL bundle"
}

export function formatPrimaryThroughputLabel(
  workloadMode?: string | null,
  primaryRateUnit?: string | null,
): string {
  const mode = resolveWorkloadMode(workloadMode)
  const unit = resolvePrimaryRateUnit(mode, primaryRateUnit)
  if (unit === "tps") return "TPS (транзакций/с)"
  return "QPS (запросов/с)"
}

export function formatSummaryUnitsLabel(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Единиц нагрузки (транзакции)"
    : "Единиц нагрузки (запросы)"
}
