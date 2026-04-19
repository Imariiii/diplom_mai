"""
API роуты для настроек системы
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

from backend.api.schemas.backup_schemas import RestoreSettings as RestoreSettingsSchema

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/restore")
async def get_restore_settings():
    """Получить настройки восстановления"""
    from backend.config import get_restore_config
    
    config = get_restore_config()
    return {
        "auto_restore": config.get("auto_restore", True),
        "verify_after_restore": config.get("verify_after_restore", True),
        "strategy": config.get("default_strategy", "sql"),
        "large_table_warning_threshold": config.get("large_table_warning_threshold", 1000000),
        "large_table_confirm_threshold": config.get("large_table_confirm_threshold", 10000000),
        "backup_table_prefix": config.get("backup_table_prefix", "_loadtest_backup_")
    }


@router.put("/restore")
async def update_restore_settings(request: RestoreSettingsSchema):
    """Обновить настройки восстановления"""
    from backend.config import update_restore_config
    
    updates = {}
    if request.auto_restore is not None:
        updates["auto_restore"] = request.auto_restore
    if request.verify_after_restore is not None:
        updates["verify_after_restore"] = request.verify_after_restore
    if request.strategy is not None:
        updates["default_strategy"] = request.strategy
    if request.large_table_warning_threshold is not None:
        updates["large_table_warning_threshold"] = request.large_table_warning_threshold
    
    updated_config = update_restore_config(updates)
    return {
        "auto_restore": updated_config.get("auto_restore", True),
        "verify_after_restore": updated_config.get("verify_after_restore", True),
        "strategy": updated_config.get("default_strategy", "sql"),
        "large_table_warning_threshold": updated_config.get("large_table_warning_threshold", 1000000)
    }