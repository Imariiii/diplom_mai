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
  scenario: string               // ID сценария тестирования (для режима scenario) - UUID из БД или строковый сценарий
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
  status: "pending" | "running" | "completed" | "failed"
  startTime: Date
  endTime?: Date
  config: TestConfig
  results?: TestResult[]
  summary?: {
    total_transactions?: number
    overall_tps?: number
    total_duration?: number
  }
  connection_names?: Record<string, string>
  connection_db_types?: Record<string, string>
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
  databaseType: string
  databaseName: string
  indexInfo?: IndexInfo
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
  
  // Внутренние метрики СУБД
  cacheHitRatio: number
  bufferPoolHitRatio: number
  lockWaits: number
  deadlocks: number
}


// ==================== Сценарии тестирования (Scenario Entity) ====================

export interface Scenario {
  id: string
  name: string
  description: string | null
  scenario_type: string
  target_connection_id?: string | null
  is_builtin: boolean | 't' | 'f'
  is_active?: boolean
  created_at: string
  updated_at: string | null
  queries_count?: number  // Количество запросов в сценарии
  queries?: ScenarioQuery[]
  indexes?: ScenarioIndex[]
}

export interface ScenarioQuery {
  id: string
  scenario_id: string
  sql_template: string
  query_type: 'select' | 'insert' | 'update' | 'delete'
  description: string | null
  weight: number
  execution_order: number
  created_at: string
  params?: ScenarioParam[]
}

export interface ScenarioParam {
  id: string
  query_id: string
  param_name: string
  param_type: 'random_int' | 'random_from_table' | 'sequential_int' | 'uuid' | 'fixed' | 'random_string' | 'random_date'
  min_value: number | null
  max_value: number | null
  table_ref: string | null
  column_ref: string | null
  fixed_value: string | null
  string_length: number | null
  created_at: string
}

export interface ScenarioIndex {
  id: string
  scenario_id: string
  table_name: string
  column_names: string
  index_type: string
  index_name: string | null
  is_unique: boolean
  condition: string | null
  description: string | null
  created_at: string
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

export interface CreateScenarioRequest {
  name: string
  description?: string
  scenario_type: string
  target_connection_id?: string
}

export interface CreateScenarioQueryRequest {
  sql_template: string
  query_type: 'select' | 'insert' | 'update' | 'delete'
  description?: string
  weight?: number
  execution_order?: number
}

export interface CreateScenarioParamRequest {
  param_name: string
  param_type: 'random_int' | 'random_from_table' | 'sequential_int' | 'uuid' | 'fixed' | 'random_string' | 'random_date'
  min_value?: number
  max_value?: number
  table_ref?: string
  column_ref?: string
  fixed_value?: string
  string_length?: number
}

export interface CreateScenarioIndexRequest {
  table_name: string
  column_names: string
  index_type?: string
  index_name?: string
  is_unique?: boolean
  condition?: string
  description?: string
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

export interface GenerateScenariosRequest {
  connection_id: string
  scenario_types?: string[]
  replace_existing?: boolean
}

export interface GenerateScenariosResponse {
  scenarios: Scenario[]
  generated_count: number
}

export interface ScenarioTemplate {
  id: TestScenario
  name: string
  description: string | null
  is_builtin: boolean
  created_at?: string | null
}

export interface ScenarioTemplateListResponse {
  templates: ScenarioTemplate[]
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
  generation_source: string
  is_active: boolean
  generated_from_connection_id?: string | null
  created_at?: string | null
  updated_at?: string | null
  queries: ScenarioQuery[]
  indexes: ScenarioIndex[]
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
