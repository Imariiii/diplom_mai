export interface Database {
  id: string
  name: string
  type: "postgresql" | "mysql" | "mariadb" | "sqlite" | "mssql"
  icon: string
}

// Режим тестирования
export type TestMode = 
  | "scenario"       // Режим со сценарием тестирования
  | "custom_query"   // Режим с конкретным SQL запросом

// Сценарии нагрузочного тестирования
export type TestScenario = 
  | "read_only"      // 100% SELECT
  | "write_only"     // 100% INSERT/UPDATE/DELETE
  | "mixed_light"    // 80% SELECT, 20% UPDATE (как TPC-C)
  | "mixed_heavy"    // 50% SELECT, 50% UPDATE
  | "oltp"           // OLTP-подобная нагрузка
  | "olap"           // OLAP-подобная нагрузка (аналитические запросы)
  | "custom"         // Пользовательский сценарий

export interface ScenarioConfig {
  id: TestScenario
  name: string
  description: string
  readPercent: number
  writePercent: number
}

// Конфигурация теста (ввод пользователя)
export interface TestConfig {
  databases: string[]           // Выбранные СУБД
  testMode: TestMode            // Режим тестирования
  scenario: TestScenario        // Сценарий тестирования (для режима scenario)
  selectedQueryId: string       // ID выбранного запроса (для режима custom_query)
  customSql: string             // Пользовательский SQL запрос
  virtualUsers: number          // Количество виртуальных пользователей (параллельных соединений)
  iterations: number            // Количество итераций на пользователя
  warmupTime: number            // Время прогрева в секундах
  queryTypes: ("read" | "write" | "mixed")[]
  dataSize: "small" | "medium" | "large"
}

export interface TestRun {
  id: string
  name: string
  status: "pending" | "running" | "completed" | "failed"
  startTime: Date
  endTime?: Date
  config: TestConfig
  results?: TestResult[]
}

// Метрики базы данных
export interface DatabaseMetrics {
  // Время отклика
  avgResponseTime: number       // Среднее время отклика (ms)
  p50ResponseTime: number       // Медиана (50-й перцентиль)
  p95ResponseTime: number       // 95-й перцентиль
  p99ResponseTime: number       // 99-й перцентиль
  minResponseTime: number       // Минимальное время
  maxResponseTime: number       // Максимальное время
  
  // Производительность
  tps: number                   // Транзакций в секунду (TPS)
  throughput: number            // Пропускная способность (req/s)
  
  // Соединения
  activeConnections: number     // Активные соединения
  
  // Ошибки
  errorCount: number            // Количество ошибок
  errorRate: number             // Процент ошибок
}

// Системные метрики
export interface SystemMetrics {
  cpuUsage: number              // Загрузка CPU (%)
  memoryUsageMB: number         // Использование RAM (MB)
  memoryUsagePercent: number    // Использование RAM (%)
  diskIOps: number              // Disk I/O (ops/sec)
  diskReadMBps: number          // Скорость чтения диска (MB/s)
  diskWriteMBps: number         // Скорость записи диска (MB/s)
  networkInMBps: number         // Входящий сетевой трафик (MB/s)
  networkOutMBps: number        // Исходящий сетевой трафик (MB/s)
}

// Метрики транзакций
export interface TransactionMetrics {
  totalTransactions: number     // Общее количество транзакций
  successfulTransactions: number // Успешные транзакции
  failedTransactions: number    // Неудачные транзакции
  rollbacks: number             // Количество откатов
}

// Внутренние метрики СУБД
export interface DBMSInternalMetrics {
  cacheHitRatio: number         // Коэффициент попаданий в кэш (%)
  bufferPoolHitRatio: number    // Коэффициент попаданий в буферный пул (%)
  lockWaits: number             // Количество ожиданий блокировок
  deadlocks: number             // Количество дедлоков
  tableSizesMB: Record<string, number>  // Размеры таблиц (MB)
  indexSizesMB: Record<string, number>  // Размеры индексов (MB)
  totalDBSizeMB: number         // Общий размер БД (MB)
}

// Полный результат теста для одной СУБД
export interface TestResult {
  databaseId: string
  databaseName: string
  metrics: DatabaseMetrics
  systemMetrics?: SystemMetrics
  transactionMetrics?: TransactionMetrics
  dbmsMetrics?: DBMSInternalMetrics
  timeSeriesData: TimeSeriesPoint[]
}

// Точка временного ряда для графиков реального времени
export interface TimeSeriesPoint {
  timestamp: number
  
  // Метрики базы данных
  responseTime: number
  throughput: number
  tps: number
  activeConnections: number
  errorCount: number
  
  // Системные метрики
  cpuUsage: number
  memoryUsage: number
  memoryUsageMB: number
  diskIOps: number
  networkIn: number
  networkOut: number
}
