/**
 * API клиент - Settings endpoints
 */

import { apiClient } from "./client"

// ==================== Настройки ====================

export async function getRestoreSettings(): Promise<{
  auto_restore: boolean
  verify_after_restore: boolean
  strategy: 'sql' | 'native'
  large_table_warning_threshold: number
  large_table_confirm_threshold: number
  backup_table_prefix: string
}> {
  return apiClient.getRestoreSettings()
}

export async function updateRestoreSettings(settings: {
  auto_restore?: boolean
  verify_after_restore?: boolean
  strategy?: 'sql' | 'native'
  large_table_warning_threshold?: number
}): Promise<{
  auto_restore: boolean
  verify_after_restore: boolean
  strategy: 'sql' | 'native'
  large_table_warning_threshold: number
}> {
  return apiClient.updateRestoreSettings(settings)
}