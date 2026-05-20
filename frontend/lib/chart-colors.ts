// Унифицированная палитра цветов для СУБД
// Используется в dashboards-page.tsx

export const DB_COLORS: Record<string, string> = {
  postgresql: "#3b82f6",  // Синий
  mysql: "#f97316",       // Оранжевый
  mariadb: "#a855f7",     // Фиолетовый
  sqlite: "#22c55e",      // Зелёный
  mssql: "#ef4444",       // Красный
}

export const DB_NAMES: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
  mariadb: "MariaDB",
  sqlite: "SQLite",
  mssql: "MS SQL Server",
}

// Функция для получения цвета СУБД
export const getDbColor = (dbId: string): string => {
  return DB_COLORS[dbId] || "#6b7280" // Серый по умолчанию
}

// Функция для получения имени СУБД
export const getDbName = (dbId: string): string => {
  return DB_NAMES[dbId] || dbId
}

// Семантические цвета серий (читаемы в light и dark)
export const CHART_SERIES_COLORS = {
  success: "#22c55e",
  error: "#ef4444",
}

// Цвета для метрик (Среднее, P95, P99)
export const METRIC_COLORS = {
  avg: "#22c55e",    // Зелёный - Среднее
  p95: "#f59e0b",   // Оранжевый - P95
  p99: "#ef4444",   // Красный - P99
}
