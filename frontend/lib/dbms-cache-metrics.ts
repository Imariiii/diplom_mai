/**
 * Отображение Cache Hit Ratio (hybrid: display verdict + raw details).
 */

export type CacheHitRatioStatus =
  | "ok"
  | "no_activity"
  | "invalid_counter"
  | "unavailable"
  | "error"
  | string

export type CacheMeaningfulness =
  | "meaningful"
  | "not_meaningful_for_workload"
  | "low_cache_activity"
  | "engine_activity_only"
  | string

export interface CacheHitDisplayInput {
  cacheHitRatio?: number | null
  cacheHitRatioStatus?: CacheHitRatioStatus | null
  cacheHitRatioNote?: string | null
  cacheHitRatioMode?: string | null
  cacheHitRatioRaw?: number | null
  cacheHitRatioRawStatus?: CacheHitRatioStatus | null
  cacheHitRatioRawNote?: string | null
  cacheHitRatioMeaningfulness?: CacheMeaningfulness | null
  cacheHitRatioScope?: string | null
  cacheHitRatioSource?: string | null
  cacheHitRatioActivityClass?: string | null
}

export function formatCacheHitPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Н/Д"
  }
  return `${Number(value).toFixed(1)}%`
}

function buildDetailsTitle(input: CacheHitDisplayInput): string | undefined {
  const parts: string[] = []
  if (input.cacheHitRatioNote) {
    parts.push(input.cacheHitRatioNote)
  }
  if (
    input.cacheHitRatioRaw !== null &&
    input.cacheHitRatioRaw !== undefined &&
    input.cacheHitRatioStatus !== "ok"
  ) {
    parts.push(
      `Raw engine-level: ${formatCacheHitPercent(input.cacheHitRatioRaw)}` +
        (input.cacheHitRatioRawStatus ? ` (${input.cacheHitRatioRawStatus})` : "")
    )
    if (input.cacheHitRatioRawNote) {
      parts.push(input.cacheHitRatioRawNote)
    }
  }
  if (input.cacheHitRatioScope) {
    parts.push(`Область: ${input.cacheHitRatioScope}`)
  }
  if (input.cacheHitRatioSource) {
    parts.push(`Источник: ${input.cacheHitRatioSource}`)
  }
  if (input.cacheHitRatioMeaningfulness) {
    parts.push(`Оценка: ${input.cacheHitRatioMeaningfulness}`)
  }
  if (input.cacheHitRatioActivityClass) {
    parts.push(`Класс нагрузки: ${input.cacheHitRatioActivityClass}`)
  }
  return parts.length > 0 ? parts.join("\n") : undefined
}

export function getCacheHitDisplay(input: CacheHitDisplayInput): {
  valueText: string
  subtitle: string
  title?: string
  details?: string
} {
  const status = input.cacheHitRatioStatus ?? "unavailable"
  const note = input.cacheHitRatioNote
  const mode = input.cacheHitRatioMode
  const details = buildDetailsTitle(input)

  if (input.cacheHitRatio !== null && input.cacheHitRatio !== undefined && status === "ok") {
    return {
      valueText: formatCacheHitPercent(input.cacheHitRatio),
      subtitle: "Доля попаданий в кэш за прогон",
      title: note ?? details,
      details,
    }
  }

  const statusMessages: Record<string, string> = {
    no_activity: "Нет информативной активности кэша для workload",
    invalid_counter: "Невалидные счётчики СУБД",
    unavailable: "Метрика недоступна",
    error: "Ошибка чтения метрики",
  }

  return {
    valueText: "Н/Д",
    subtitle: mode === "delta" ? "Вердикт за прогон" : "Кэш",
    title: note ?? statusMessages[status] ?? "Недостаточно данных для расчёта",
    details,
  }
}

export function mapRawDbmsCacheFields(raw: Record<string, unknown> | null | undefined): CacheHitDisplayInput & {
  cacheHitRatio: number | null
  bufferPoolHitRatio: number | null
} {
  if (!raw) {
    return { cacheHitRatio: null, bufferPoolHitRatio: null }
  }

  const parseRatio = (key: string): number | null => {
    const v = raw[key]
    if (v === null || v === undefined) return null
    return Number.isFinite(Number(v)) ? Number(v) : null
  }

  const ratio = parseRatio("cache_hit_ratio")
  const buffer = parseRatio("buffer_pool_hit_ratio") ?? ratio

  return {
    cacheHitRatio: ratio,
    bufferPoolHitRatio: buffer,
    cacheHitRatioStatus: (raw.cache_hit_ratio_status as CacheHitRatioStatus) ?? undefined,
    cacheHitRatioNote: (raw.cache_hit_ratio_note as string) ?? undefined,
    cacheHitRatioMode: (raw.cache_hit_ratio_mode as string) ?? undefined,
    cacheHitRatioRaw: parseRatio("cache_hit_ratio_raw"),
    cacheHitRatioRawStatus: (raw.cache_hit_ratio_raw_status as CacheHitRatioStatus) ?? undefined,
    cacheHitRatioRawNote: (raw.cache_hit_ratio_raw_note as string) ?? undefined,
    cacheHitRatioMeaningfulness: (raw.cache_hit_ratio_meaningfulness as CacheMeaningfulness) ?? undefined,
    cacheHitRatioScope: (raw.cache_hit_ratio_scope as string) ?? undefined,
    cacheHitRatioSource: (raw.cache_hit_ratio_source as string) ?? undefined,
    cacheHitRatioActivityClass: (raw.cache_hit_ratio_activity_class as string) ?? undefined,
  }
}
