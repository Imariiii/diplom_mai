/**
 * Нормализация метрик пропускной способности (обратная совместимость со старыми прогонами).
 *
 * throughput — успешных primary units/с: успешных запросов/с в query-mode,
 * успешных транзакций/с в transaction-mode;
 * attempt_rate — всех primary unit попыток/с (realtime и итоговая интенсивность).
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

/** Значение всех primary unit попыток/с для точки временного ряда. */
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

/** Attempt rate в карточке: live во время теста, итог после завершения. */
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

/** Successful primary throughput: live во время теста, итог после завершения. */
export function formatCardSuccessfulThroughput(options: {
  isTestFinished: boolean
  throughput?: number
  liveThroughput?: string
}): string {
  const { isTestFinished, throughput, liveThroughput } = options
  if (isTestFinished) {
    return typeof throughput === "number" ? throughput.toFixed(0) : "—"
  }
  return liveThroughput && liveThroughput.trim() !== "" ? liveThroughput : "—"
}

/** Успешных операций/с для точки time_series (колонка tps). */
export function timeSeriesSuccessfulThroughput(raw: {
  tps?: number | null
  throughput?: number | null
}): number {
  const value = raw.tps
  return typeof value === "number" ? value : 0
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

/** Короткая подпись для бейджа в UI конфигурации и сценариев. */
export function formatWorkloadModeBadge(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction" ? "Транзакции" : "Запросы"
}

export function getWorkloadModeBadgeVariant(
  workloadMode?: string | null,
): "outline" | "secondary" {
  return resolveWorkloadMode(workloadMode) === "transaction" ? "secondary" : "outline"
}

export function formatPrimaryThroughputLabel(
  workloadMode?: string | null,
  primaryRateUnit?: string | null,
): string {
  const mode = resolveWorkloadMode(workloadMode)
  const unit = resolvePrimaryRateUnit(mode, primaryRateUnit)
  if (unit === "tps") return "Успешных транзакций/с"
  return "Успешных запросов/с"
}

export function formatAttemptRateLabel(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Транзакций/с"
    : "Запросов/с"
}

export function formatAttemptRateDescription(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Все завершённые транзакции в секунду, включая ошибки"
    : "Все завершённые запросы в секунду, включая ошибки"
}

export function formatPrimaryThroughputDescription(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Только успешные транзакции за окно сэмпла"
    : "Только успешные SQL-операции за окно сэмпла"
}

export function formatWindowUnitsLabel(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Транзакций в окне"
    : "Запросов в окне"
}

export function formatWindowUnitsDescription(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Завершённые транзакции в последнем окне (~1 с)"
    : "Завершённые запросы в последнем окне (~1 с)"
}

export function formatSummaryUnitsLabel(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "Единиц нагрузки (транзакции)"
    : "Единиц нагрузки (запросы)"
}

/** Единица успешной пропускной способности для сравнения результатов. */
export function formatComparisonThroughputRateUnit(workloadMode?: string | null): string {
  return resolveWorkloadMode(workloadMode) === "transaction"
    ? "транзакций/с"
    : "запросов/с"
}

export function formatComparisonThroughputTitle(workloadMode?: string | null): string {
  const unit = formatComparisonThroughputRateUnit(workloadMode)
  return `Пропускная способность (${unit})`
}

export function formatComparisonThroughputMeanLabel(workloadMode?: string | null): string {
  return `Пропускная способность (среднее, ${formatComparisonThroughputRateUnit(workloadMode)})`
}

export function formatComparisonThroughputMedianLabel(workloadMode?: string | null): string {
  return `Пропускная способность (медиана, ${formatComparisonThroughputRateUnit(workloadMode)})`
}

export function formatComparisonThroughputCvLabel(workloadMode?: string | null): string {
  return `Вариативность пропускной способности (CV)`
}

export function formatComparisonThroughputValue(
  value: number | null | undefined,
  workloadMode?: string | null,
  digits = 0,
): string {
  if (value == null) return "—"
  return `${value.toFixed(digits)} ${formatComparisonThroughputRateUnit(workloadMode)}`
}

type ComparisonWorkloadSource = {
  scenario_info?: { workload_mode?: string | null } | null
  config?: Record<string, unknown> | null
}

export function resolveComparisonWorkloadModeFromTest(
  test?: ComparisonWorkloadSource | null,
): WorkloadMode {
  if (!test) return "query"
  const config = test.config ?? {}
  const fromScenario = test.scenario_info?.workload_mode
  const fromConfig = typeof config.workload_mode === "string" ? config.workload_mode : null
  return resolveWorkloadMode(fromScenario ?? fromConfig)
}

export function resolveComparisonWorkloadMode(result: {
  analysis_mode: string
  test?: ComparisonWorkloadSource | null
  tests?: ComparisonWorkloadSource[] | null
}): WorkloadMode {
  if (result.analysis_mode === "per_test") {
    return resolveComparisonWorkloadModeFromTest(result.test)
  }
  const tests = result.tests ?? []
  if (tests.length === 0) return "query"
  const modes = new Set(tests.map((test) => resolveComparisonWorkloadModeFromTest(test)))
  if (modes.size === 1) {
    return [...modes][0]
  }
  return "query"
}

export interface ComparisonMetricRow {
  key: string
  label: string
  better: "lower" | "higher"
  isCore: boolean
  unit: string
  accessor: (bundle: ComparisonStatsBundle | undefined) => number | null | undefined
  format: (value: number | null | undefined) => string
}

type ComparisonStatsBundle = {
  latency_ms?: {
    mean?: number | null
    median?: number | null
    p95?: number | null
    p99?: number | null
    cv?: number | null
    min?: number | null
    max?: number | null
    iqr?: number | null
  } | null
  throughput?: {
    mean?: number | null
    median?: number | null
    cv?: number | null
  } | null
  error_rate?: number | null
  total_duration_sec?: number | null
}

export function buildComparisonMetricRows(workloadMode?: string | null): ComparisonMetricRow[] {
  const tpUnit = formatComparisonThroughputRateUnit(workloadMode)
  const formatTp = (value: number | null | undefined) =>
    value == null ? "—" : `${value.toFixed(0)} ${tpUnit}`

  return [
    {
      key: "latency_mean",
      label: "Задержка (среднее)",
      better: "lower",
      isCore: true,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.mean,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_median",
      label: "Задержка (медиана)",
      better: "lower",
      isCore: true,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.median,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_p95",
      label: "Задержка p95",
      better: "lower",
      isCore: true,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.p95,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_p99",
      label: "Задержка p99",
      better: "lower",
      isCore: true,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.p99,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_cv",
      label: "Вариативность задержки (CV)",
      better: "lower",
      isCore: true,
      unit: "%",
      accessor: (b) => b?.latency_ms?.cv,
      format: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`),
    },
    {
      key: "throughput_mean",
      label: formatComparisonThroughputMeanLabel(workloadMode),
      better: "higher",
      isCore: true,
      unit: tpUnit,
      accessor: (b) => b?.throughput?.mean,
      format: formatTp,
    },
    {
      key: "error_rate",
      label: "Доля ошибок",
      better: "lower",
      isCore: true,
      unit: "%",
      accessor: (b) => b?.error_rate,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)}%`),
    },
    {
      key: "duration",
      label: "Общее время",
      better: "lower",
      isCore: true,
      unit: "с",
      accessor: (b) => b?.total_duration_sec,
      format: (v) => (v == null ? "—" : `${v.toFixed(1)} с`),
    },
    {
      key: "latency_min",
      label: "Задержка (мин)",
      better: "lower",
      isCore: false,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.min,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_max",
      label: "Задержка (макс)",
      better: "lower",
      isCore: false,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.max,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "latency_iqr",
      label: "Задержка IQR",
      better: "lower",
      isCore: false,
      unit: "мс",
      accessor: (b) => b?.latency_ms?.iqr,
      format: (v) => (v == null ? "—" : `${v.toFixed(2)} мс`),
    },
    {
      key: "throughput_median",
      label: formatComparisonThroughputMedianLabel(workloadMode),
      better: "higher",
      isCore: false,
      unit: tpUnit,
      accessor: (b) => b?.throughput?.median,
      format: formatTp,
    },
    {
      key: "throughput_cv",
      label: formatComparisonThroughputCvLabel(workloadMode),
      better: "lower",
      isCore: false,
      unit: "%",
      accessor: (b) => b?.throughput?.cv,
      format: (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`),
    },
  ]
}
