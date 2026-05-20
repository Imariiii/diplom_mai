/**
 * Нормализация и генерация названий нагрузочных прогонов.
 */

/** Пустая строка или только пробелы → undefined (автоимя на сервере/клиенте). */
export function normalizeTestDisplayName(raw: string | undefined): string | undefined {
  if (raw === undefined) return undefined
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

/** Имя по умолчанию при пустом поле (формат совпадает с backend). */
export function buildDefaultTestRunName(date: Date = new Date()): string {
  const day = String(date.getDate()).padStart(2, "0")
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, "0")
  const minutes = String(date.getMinutes()).padStart(2, "0")
  return `Тест ${day}.${month}.${year} ${hours}:${minutes}`
}

/** Итоговое имя для запуска: пользовательское или автогенерация. */
export function resolveTestRunName(raw: string | undefined): string {
  return normalizeTestDisplayName(raw) ?? buildDefaultTestRunName()
}

/** Подпись для сводки: пользовательское имя или пометка об автогенерации. */
export function formatTestRunNameForSummary(raw: string | undefined): string {
  const custom = normalizeTestDisplayName(raw)
  if (custom) return custom
  return `(авто) ${buildDefaultTestRunName()}`
}

/** Поле содержит только пробелы — ошибка ввода. */
export function isWhitespaceOnlyTestDisplayName(raw: string | undefined): boolean {
  return raw !== undefined && raw.length > 0 && normalizeTestDisplayName(raw) === undefined
}
