/**
 * API клиент - Database State endpoints
 */

import { apiClient } from "./client"

// ==================== Database State Management ====================

export async function getDatabaseState(connectionId: string): Promise<{
  connection_id: string
  connection_name: string
  dbms_type: string
  tables: Record<string, { row_count: number; has_backup: boolean }>
  has_pending_backups: boolean
  backup_tables: string[]
  status: 'clean' | 'modified' | 'backup_exists'
}> {
  return apiClient.getDatabaseState(connectionId)
}

export async function createBackup(connectionId: string, tables?: string[]): Promise<{
  backup_id: string
  dbms_type: string
  tables: string[]
  row_counts: Record<string, number>
  created_at: string
}> {
  return apiClient.createBackup(connectionId, tables)
}

export async function restoreBackup(connectionId: string, backupId?: string): Promise<{
  success: boolean
  duration_ms: number
  verified: boolean
  errors: string[]
}> {
  return apiClient.restoreBackup(connectionId, backupId)
}

export async function cleanupBackups(connectionId: string): Promise<{
  deleted_tables: string[]
}> {
  return apiClient.cleanupBackups(connectionId)
}

export async function estimateBackup(connectionId: string, tables: string[]): Promise<{
  tables: Record<string, { rows: number; size_bytes: number }>
  total_rows: number
  total_size_bytes: number
  estimated_time_sec: number
  warnings: string[]
}> {
  return apiClient.estimateBackup(connectionId, tables)
}
