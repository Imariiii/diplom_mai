"""
Pydantic схемы для профилей модели данных и logical templates.
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.api.schemas.connection_schemas import SchemaProfileSummaryResponse


class ScenarioTemplateResponse(BaseModel):
    """Логический шаблон сценария нагрузки."""
    id: str
    name: str
    description: Optional[str] = None
    is_builtin: bool
    created_at: Optional[str] = None


class ConnectionProfileAssignRequest(BaseModel):
    """Запрос на назначение или создание профиля для подключения."""
    schema_profile_id: Optional[str] = None
    profile_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    reference_connection_id: Optional[str] = None
    profile_source: str = "manual"


class SchemaProfileCreateRequest(BaseModel):
    """Создание нового профиля схемы."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    reference_connection_id: Optional[str] = None


class ScenarioBundleSummaryResponse(BaseModel):
    """Краткая информация о каноническом bundle."""
    id: str
    schema_profile_id: str
    schema_profile_name: Optional[str] = None
    scenario_template_id: str
    scenario_template_name: Optional[str] = None
    name: str
    generation_source: str
    is_active: bool
    generated_from_connection_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    queries: list[dict] = []
    indexes: list[dict] = []


class ProfileBundleGenerateRequest(BaseModel):
    """Запрос на генерацию profile-centric bundle'ов."""
    reference_connection_id: Optional[str] = None
    scenario_template_ids: Optional[List[str]] = None


class SchemaProfileDetailResponse(SchemaProfileSummaryResponse):
    """Детальный профиль с его bundle'ами."""
    bundles: list[ScenarioBundleSummaryResponse] = []


class ScenarioTemplateListResponse(BaseModel):
    """Список logical templates."""
    templates: list[ScenarioTemplateResponse]


class SchemaProfileListResponse(BaseModel):
    """Список schema profiles."""
    profiles: list[SchemaProfileSummaryResponse]


class SchemaProfileBundlesResponse(BaseModel):
    """Ответ генерации bundle'ов профиля."""
    profile: SchemaProfileSummaryResponse
    bundles: list[ScenarioBundleSummaryResponse]
    generated_count: int
