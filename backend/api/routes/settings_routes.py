"""
API роуты для настроек системы
"""
from fastapi import APIRouter

from backend.api.schemas.backup_schemas import RestoreSettings as RestoreSettingsSchema

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/restore")
async def get_restore_settings():
    """Получить настройки восстановления"""
    from backend.core.config import settings
    
    return {
        "auto_restore": settings.restore.auto_restore,
        "verify_after_restore": settings.restore.verify_after_restore,
        "strategy": settings.restore.default_strategy,
        "large_table_warning_threshold": settings.restore.large_table_warning_threshold,
        "large_table_confirm_threshold": settings.restore.large_table_confirm_threshold,
        "backup_table_prefix": settings.restore.backup_table_prefix
    }


@router.put("/restore")
async def update_restore_settings(request: RestoreSettingsSchema):
    """Обновить настройки восстановления"""
    from backend.core.config import settings

    if request.auto_restore is not None:
        settings.restore.auto_restore = request.auto_restore
    if request.verify_after_restore is not None:
        settings.restore.verify_after_restore = request.verify_after_restore
    if request.strategy is not None:
        settings.restore.default_strategy = request.strategy
    if request.large_table_warning_threshold is not None:
        settings.restore.large_table_warning_threshold = request.large_table_warning_threshold
    
    return {
        "auto_restore": settings.restore.auto_restore,
        "verify_after_restore": settings.restore.verify_after_restore,
        "strategy": settings.restore.default_strategy,
        "large_table_warning_threshold": settings.restore.large_table_warning_threshold
    }