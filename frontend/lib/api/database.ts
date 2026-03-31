/**
 * API клиент - Database State endpoints
 */

import { apiClient } from "./client"

// ==================== Database State Management ====================

export async function getDatabaseState(dbmsType: string): Promise<{
  dbms_type: string
  tables: Record<string, { row_count: number; has_backup: boolean }>
  has_pending_backups: boolean
  backup_tables: string[]
  status: 'clean' | 'modified' | 'backup_exists'
}> {
  return apiClient.getDatabaseState(dbmsType)
}

export async function createBackup(dbmsType: string, tables?: string[]): Promise<{
  backup_id: string
  dbms_type: string
  tables: string[]
  row_counts: Record<string, number>
  created_at: string
}> {
  return apiClient.createBackup(dbmsType, tables)
}

export async function restoreBackup(dbmsType: string, backupId?: string): Promise<{
  success: boolean
  duration_ms: number
  verified: boolean
  errors: string[]
}> {
  return apiClient.restoreBackup(dbmsType, backupId)
}

export async function cleanupBackups(dbmsType: string): Promise<{
  deleted_tables: string[]
}> {
  return apiClient.cleanupBackups(dbmsType)
}

export async function estimateBackup(dbmsType: string, tables: string[]): Promise<{
  tables: Record<string, { rows: number; size_bytes: number }>
  total_rows: number
  total_size_bytes: number
  estimated_time_sec: number
  warnings: string[]
}> {
  return apiClient.estimateBackup(dbmsType, tables)
}