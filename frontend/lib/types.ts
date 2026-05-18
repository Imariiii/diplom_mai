// Режим тестирования
export type TestMode = 
  | "scenario"       // Режим со сценарием тестирования
  | "custom_query"   // Режим с конкретным SQL запросом

// Logical template id или пользовательский custom template id
export type TestScenario = string

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
  scenario: string              // ID logical template
  bundleId?: string             // Опционально: явный bundle variant
  useIndexes: boolean           // Создавать индексы сценария перед тестом
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
  status: "pending" | "running" | "cancelling" | "cancelled" | "completed" | "failed"
  startTime: Date
  endTime?: Date
  config: TestConfig
  results?: TestResult[]
  summary?: {
    total_transactions?: number
    total_duration?: number
  }
  error?: string | null
  connection_names?: Record<string, string>
  connection_db_types?: Record<string, string>
}

export interface SelfCheckWarningSummary {
  warnings: string[]
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
  
  // Производительность (одна SQL-операция = один запрос + commit)
  throughput: number            // Успешных запросов в секунду
  attemptRate?: number          // Всех запросов в секунду (успех + ошибка), итог прогона
  
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
  cacheHitRatio: number | null  // Доля попаданий в кэш за прогон (%), null = Н/Д
  bufferPoolHitRatio?: number | null
  cacheHitRatioStatus?: "ok" | "no_activity" | "invalid_counter" | "unavailable" | "error"
  cacheHitRatioNote?: string
  cacheHitRatioMode?: "delta" | string
  lockWaits: number             // Количество ожиданий блокировок
  lockWaitsMode?: "current" | "delta" | "sampled_max"
  deadlocks: number             // Количество дедлоков
  deadlocksMode?: "current" | "delta" | "sampled_max"
  tableSizesMB: Record<string, number>  // Размеры таблиц (MB)
  indexSizesMB: Record<string, number>  // Размеры индексов (MB)
  totalDBSizeMB: number         // Общий размер БД (MB)
}

// Полный результат теста для одной СУБД
export interface TestResult {
  databaseId: string
  databaseType: string
  databaseName: string
  indexInfo?: IndexInfo
  selfCheckWarnings?: string[]
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
  /** Live: запросов SQL/с за окно (~1 с). */
  attemptRate: number
  activeConnections: number
  errorCount: number
  
  // Системные метрики
  cpuUsage: number
  memoryUsage: number
  memoryUsageMB: number
  diskIOps: number
  networkIn: number
  networkOut: number
  
  // Внутренние метрики СУБД
  cacheHitRatio?: number | null
  bufferPoolHitRatio?: number | null
  cacheHitRatioStatus?: "ok" | "no_activity" | "invalid_counter" | "unavailable" | "error"
  cacheHitRatioNote?: string
  cacheHitRatioMode?: string
  lockWaits: number
  deadlocks: number
}


// ==================== Bundle-centric сценарии ====================

export interface ScenarioQuery {
  id?: string
  bundle_id?: string
  sql_template: string
  query_type: 'select' | 'insert' | 'update' | 'delete' | string
  description: string | null
  weight: number
  order_index: number
  created_at?: string | null
  params?: ScenarioParam[]
}

export interface ScenarioParam {
  id?: string
  query_id?: string
  param_name: string
  param_type: 'random_int' | 'random_from_table' | 'sequential_int' | 'uuid' | 'fixed' | 'random_string' | 'random_date' | string
  min_value: number | null
  max_value: number | null
  fixed_value?: string | null
  string_pattern?: string | null
  table_ref: string | null
  column_ref: string | null
  string_length: number | null
  current_value?: number | null
  step?: number | null
  created_at?: string | null
}

export interface ScenarioIndex {
  id?: string
  bundle_id?: string
  table_name: string
  column_names: string
  index_type: string
  index_name: string | null
  is_unique: boolean
  condition: string | null
  description: string | null
  created_at?: string | null
}

export interface IndexInfoDetail {
  name: string
  table: string
  columns: string
  index_type: string
  creation_time_ms?: number
  drop_time_ms?: number
  success: boolean
  error?: string | null
}

export interface IndexInfo {
  enabled: boolean
  indexes_count: number
  total_creation_time_ms: number
  drop_time_ms: number
  details: IndexInfoDetail[]
  drop_details?: IndexInfoDetail[]
  errors?: string[]
  drop_errors?: string[]
}

// ==================== Database State Management Types ====================

export interface DatabaseState {
  connection_id: string
  connection_name: string
  dbms_type: string
  tables: Record<string, {
    row_count: number
    has_backup: boolean
  }>
  has_pending_backups: boolean
  backup_tables: string[]
  pending_backup_count: number
  pending_backup_strategy: "sql" | "native" | null
  status: 'clean' | 'modified' | 'backup_exists'
}


export interface RestoreSettings {
  auto_restore: boolean
  verify_after_restore: boolean
  strategy: 'sql' | 'native'
  large_table_warning_threshold: number
  large_table_confirm_threshold: number
  backup_table_prefix: string
}


// ==================== Logical Database Types ====================

export interface LogicalDatabase {
  id: string
  name: string
  description: string | null
  schema_profile_id?: string | null
  schema_profile_name?: string | null
  reference_connection_id?: string | null
  reference_connection_name?: string | null
  profile_status?: 'draft' | 'confirmed' | 'needs_review' | 'incompatible' | string
  compatibility_status?: 'unknown' | 'valid' | 'valid_with_warnings' | 'invalid' | string
  compatibility_report?: LogicalDatabaseCompatibilityReport | null
  validated_at?: string | null
  created_at: string | null
  updated_at: string | null
}

export interface LogicalDatabaseWithConnections extends LogicalDatabase {
  connections: DatabaseConnection[]
}

export interface LogicalDatabaseDetail extends LogicalDatabaseWithConnections {
  bundles: ScenarioBundleSummary[]
}

export interface LogicalDatabaseCreateRequest {
  name: string
  description?: string
  schema_profile_id?: string
}

export interface LogicalDatabaseUpdateRequest {
  name?: string
  description?: string
  schema_profile_id?: string
}

export interface LogicalDatabaseProfileAssignRequest {
  schema_profile_id?: string
  profile_name?: string
  description?: string
  reference_connection_id?: string
  profile_source?: string
}

export interface LogicalDatabaseReferenceUpdateRequest {
  reference_connection_id: string
}

export interface LogicalDatabaseCompatibilityReport {
  valid: boolean
  errors: string[]
  warnings: string[]
  reference_connection_id?: string | null
  reference_connection_name?: string | null
  mode?: string
  connections?: Array<{ id: string; name: string; dbms_type: string }>
}

export interface LogicalDatabaseListResponse {
  databases: LogicalDatabaseWithConnections[]
}

export interface LogicalDatabaseBundlesGenerateResponse {
  logical_database: LogicalDatabaseDetail
  generated_count: number
}

// ==================== Database Connection Management Types ====================

export type SupportedDbmsType = "mysql" | "mariadb" | "postgresql"

export interface DatabaseConnection {
  id: string
  name: string
  dbms_type: SupportedDbmsType
  host: string
  port: number
  user: string
  database: string
  group: string | null
  logical_database_id?: string | null
  logical_database_name?: string | null
  schema_profile_id?: string | null
  schema_profile_name?: string | null
  detected_profile_name?: string | null
  profile_confidence?: number | null
  profile_source?: string | null
  is_active: boolean
  extra_params: Record<string, unknown> | null
  created_at: string | null
  updated_at: string | null
}

export interface ConnectionCreateRequest {
  name: string
  dbms_type: SupportedDbmsType
  host: string
  port: number
  user: string
  password: string
  database: string
  group?: string
  logical_database_id?: string
  extra_params?: Record<string, unknown>
}

export interface ConnectionUpdateRequest {
  name?: string
  dbms_type?: string
  host?: string
  port?: number
  user?: string
  password?: string
  database?: string
  group?: string
  logical_database_id?: string
  is_active?: boolean
  extra_params?: Record<string, unknown>
}

export interface ConnectionTestRequest {
  host: string
  port: number
  user: string
  password: string
  database: string
  dbms_type: SupportedDbmsType
  extra_params?: Record<string, unknown>
}

export interface ConnectionTestResponse {
  success: boolean
  message: string
  response_time_ms: number | null
}

export interface ConnectionListResponse {
  connections: DatabaseConnection[]
  groups: string[]
}

export interface ConnectionGroupsResponse {
  groups: string[]
}

export interface SchemaColumn {
  name: string
  data_type: string
  is_nullable: boolean
  is_primary_key: boolean
  is_unique: boolean
  column_default: string | null
  category: string
}

export interface SchemaForeignKey {
  constraint_name: string
  from_table: string
  from_column: string
  to_table: string
  to_column: string
}

export interface SchemaTable {
  name: string
  columns: SchemaColumn[]
  primary_key: string[]
  row_count: number
  foreign_keys_out: SchemaForeignKey[]
  foreign_keys_in: SchemaForeignKey[]
  unique_columns: string[]
  capabilities: string[]
}

export interface ConnectionSchemaPreview {
  connection_id: string
  connection_name: string
  dbms_type: SupportedDbmsType
  total_tables: number
  tables: SchemaTable[]
  current_profile?: SchemaProfileSummary | null
  suggested_profile?: SchemaProfileSuggestion | null
  available_scenario_types: string[]
  matching_templates: Record<string, string[]>
}

export interface ScenarioTemplate {
  id: string
  name: string
  description: string | null
  is_builtin: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface ScenarioTemplateListResponse {
  templates: ScenarioTemplate[]
}

export interface ScenarioTemplateCreateRequest {
  name: string
  description?: string
}

export interface ScenarioTemplateUpdateRequest {
  name?: string
  description?: string
}

export interface SchemaProfileSummary {
  id: string
  name: string
  description: string | null
  detection_mode?: string | null
  reference_connection_id?: string | null
  is_builtin: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface SchemaProfileSuggestion {
  name: string
  description: string
  confidence: number
  reason: string
  existing_profile_id?: string | null
  is_existing: boolean
}

export interface ConnectionProfileAssignRequest {
  schema_profile_id?: string
  profile_name?: string
  description?: string
  reference_connection_id?: string
  profile_source?: string
}

export interface SchemaProfileListResponse {
  profiles: SchemaProfileSummary[]
}

export interface ScenarioBundleSummary {
  id: string
  schema_profile_id: string
  schema_profile_name?: string | null
  scenario_template_id: string
  scenario_template_name?: string | null
  name: string
  description?: string | null
  generation_source: string
  is_builtin: boolean
  is_active: boolean
  generated_from_connection_id?: string | null
  created_at?: string | null
  updated_at?: string | null
  queries: ScenarioQuery[]
  indexes: ScenarioIndex[]
}

export interface ScenarioBundleSaveRequest {
  scenario_template_id: string
  name: string
  description?: string
  generation_source?: string
  generated_from_connection_id?: string
  is_active: boolean
  queries: ScenarioQuery[]
  indexes: ScenarioIndex[]
}

export interface ScenarioBundleCloneRequest {
  name: string
}

export interface SchemaProfileDetail extends SchemaProfileSummary {
  bundles: ScenarioBundleSummary[]
}

export interface ProfileBundleGenerateRequest {
  reference_connection_id?: string
  scenario_template_ids?: string[]
}

export interface ProfileBundleGenerateResponse {
  profile: SchemaProfileSummary
  bundles: ScenarioBundleSummary[]
  generated_count: number
}
