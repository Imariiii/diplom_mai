"""
Pydantic схемы для резервного копирования и восстановления БД
"""
from pydantic import BaseModel
from typing import List, Optional, Dict


class BackupRequest(BaseModel):
    """Запрос на создание резервной копии"""
    tables: Optional[List[str]] = None


class BackupResponse(BaseModel):
    """Ответ с информацией о созданной резервной копии"""
    backup_id: str
    dbms_type: str
    tables: List[str]
    row_counts: Dict[str, int]
    created_at: str


class RestoreRequest(BaseModel):
    """Запрос на восстановление из резервной копии"""
    backup_id: Optional[str] = None


class RestoreResponse(BaseModel):
    """Ответ с результатами восстановления"""
    success: bool
    duration_ms: float
    verified: bool
    errors: List[str]


class CleanupResponse(BaseModel):
    """Ответ после очистки backup-таблиц"""
    deleted_tables: List[str]


class EstimateResponse(BaseModel):
    """Ответ с оценкой размера резервной копии"""
    tables: Dict[str, Dict]
    total_rows: int
    total_size_bytes: int
    estimated_time_sec: float
    warnings: List[str]


class RestoreSettings(BaseModel):
    """Настройки восстановления"""
    auto_restore: Optional[bool] = None
    verify_after_restore: Optional[bool] = None
    strategy: Optional[str] = None
    large_table_warning_threshold: Optional[int] = None