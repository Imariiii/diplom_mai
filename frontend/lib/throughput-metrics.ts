/**
 * Нормализация метрик пропускной способности (обратная совместимость со старыми прогонами).
 *
 * throughput — успешных SQL-операций/с (итог прогона);
 * attempt_rate — всех попыток/с (realtime и итоговая интенсивность).
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

/** Значение попыток/с для точки временного ряда (live хранится в throughput или attempt_rate). */
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
