// Унифицированная палитра цветов для СУБД
// Используется в dashboards-page.tsx и reports-page.tsx

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

// Цвета для графиков
export const CHART_COLORS = {
  axis: "#9CA3AF",      // Цвет осей
  text: "#ffffff",      // Цвет текста
  success: "#22c55e",   // Зелёный для успешных операций
  error: "#ef4444",     // Красный для ошибок
}
