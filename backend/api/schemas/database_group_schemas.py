"""
Pydantic схемы для управления группами баз данных
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from backend.api.schemas.profile_schemas import ScenarioBundleSummaryResponse


class DatabaseGroupCreateRequest(BaseModel):
    """Запрос на создание группы баз данных"""
    name: str = Field(..., min_length=1, max_length=255, description="Уникальное название группы баз данных")
    description: Optional[str] = Field(default=None, description="Описание датасета / модели данных")
    schema_profile_id: Optional[str] = Field(default=None, description="ID schema_profile для database group")


class DatabaseGroupUpdateRequest(BaseModel):
    """Запрос на обновление группы баз данных (все поля опциональны)"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    schema_profile_id: Optional[str] = Field(default=None, description="ID schema_profile для database group")


class DatabaseGroupProfileAssignRequest(BaseModel):
    """Назначение профиля модели данных группы баз данных."""
    schema_profile_id: Optional[str] = None
    profile_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    reference_connection_id: Optional[str] = None
    profile_source: str = "manual"


class DatabaseGroupConnectionSummary(BaseModel):
    """Краткая информация о подключении внутри группы баз данных"""
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


class DatabaseGroupResponse(BaseModel):
    """Ответ с информацией о группы баз данных"""
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
    connections: List[DatabaseGroupConnectionSummary] = Field(default_factory=list)


class DatabaseGroupDetailResponse(DatabaseGroupResponse):
    """Детальная информация о группы баз данных вместе с bundle'ами."""
    bundles: List[ScenarioBundleSummaryResponse] = Field(default_factory=list)


class DatabaseGroupListResponse(BaseModel):
    """Список групп баз данных"""
    groups: List[DatabaseGroupResponse]


class DatabaseGroupBundlesGenerateResponse(BaseModel):
    """Ответ генерации bundle'ов для database group."""
    database_group: DatabaseGroupDetailResponse
    generated_count: int


class DatabaseGroupReferenceUpdateRequest(BaseModel):
    """Назначение эталонного подключения database group."""
    reference_connection_id: str = Field(..., min_length=1)


class DatabaseGroupValidationResponse(BaseModel):
    """Результат проверки совместимости database group."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reference_connection_id: Optional[str] = None
    reference_connection_name: Optional[str] = None
    mode: str = "lenient"
    connections: List[dict] = Field(default_factory=list)
    bundle_preflight: Dict[str, dict] = Field(default_factory=dict)
