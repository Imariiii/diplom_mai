"""
Pydantic схемы для управления логическими базами данных
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from backend.api.schemas.profile_schemas import ScenarioBundleSummaryResponse


class LogicalDatabaseCreateRequest(BaseModel):
    """Запрос на создание логической базы данных"""
    name: str = Field(..., min_length=1, max_length=255, description="Уникальное название логической БД")
    description: Optional[str] = Field(default=None, description="Описание датасета / модели данных")
    schema_profile_id: Optional[str] = Field(default=None, description="ID schema_profile для logical database")


class LogicalDatabaseUpdateRequest(BaseModel):
    """Запрос на обновление логической базы данных (все поля опциональны)"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    schema_profile_id: Optional[str] = Field(default=None, description="ID schema_profile для logical database")


class LogicalDatabaseProfileAssignRequest(BaseModel):
    """Назначение профиля модели данных логической БД."""
    schema_profile_id: Optional[str] = None
    profile_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    reference_connection_id: Optional[str] = None
    profile_source: str = "manual"


class LogicalDatabaseConnectionSummary(BaseModel):
    """Краткая информация о подключении внутри логической БД"""
    id: str
    name: str
    dbms_type: str
    host: str
    port: int
    database: str
    group: Optional[str] = None
    schema_profile_id: Optional[str] = None
    schema_profile_name: Optional[str] = None
    detected_profile_name: Optional[str] = None
    profile_confidence: Optional[float] = None
    profile_source: Optional[str] = None
    is_active: bool


class LogicalDatabaseResponse(BaseModel):
    """Ответ с информацией о логической БД"""
    id: str
    name: str
    description: Optional[str] = None
    schema_profile_id: Optional[str] = None
    schema_profile_name: Optional[str] = None
    reference_connection_id: Optional[str] = None
    reference_connection_name: Optional[str] = None
    profile_status: str = "draft"
    compatibility_status: str = "unknown"
    compatibility_report: Optional[dict] = None
    validated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    connections: List[LogicalDatabaseConnectionSummary] = Field(default_factory=list)


class LogicalDatabaseDetailResponse(LogicalDatabaseResponse):
    """Детальная информация о логической БД вместе с bundle'ами."""
    bundles: List[ScenarioBundleSummaryResponse] = Field(default_factory=list)


class LogicalDatabaseListResponse(BaseModel):
    """Список логических БД"""
    databases: List[LogicalDatabaseResponse]


class LogicalDatabaseBundlesGenerateResponse(BaseModel):
    """Ответ генерации bundle'ов для logical database."""
    logical_database: LogicalDatabaseDetailResponse
    generated_count: int


class LogicalDatabaseReferenceUpdateRequest(BaseModel):
    """Назначение эталонного подключения logical database."""
    reference_connection_id: str = Field(..., min_length=1)


class LogicalDatabaseValidationResponse(BaseModel):
    """Результат проверки совместимости logical database."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reference_connection_id: Optional[str] = None
    reference_connection_name: Optional[str] = None
    mode: str = "lenient"
    connections: List[dict] = Field(default_factory=list)
    bundle_preflight: Dict[str, dict] = Field(default_factory=dict)
