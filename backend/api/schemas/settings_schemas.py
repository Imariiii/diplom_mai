"""
Pydantic схемы для настроек системы
"""
from pydantic import BaseModel
from typing import Optional


class SettingsResponse(BaseModel):
    """Ответ с текущими настройками восстановления"""
    auto_restore: bool
    verify_after_restore: bool
    strategy: str
    large_table_warning_threshold: int
    large_table_confirm_threshold: int
    backup_table_prefix: str


class SettingsUpdateRequest(BaseModel):
    """Запрос на обновление настроек восстановления"""
    auto_restore: Optional[bool] = None
    verify_after_restore: Optional[bool] = None
    strategy: Optional[str] = None
    large_table_warning_threshold: Optional[int] = None