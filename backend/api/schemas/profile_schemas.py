"""
Pydantic схемы для профилей модели данных и bundle-centric logical templates.
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
    updated_at: Optional[str] = None


class ScenarioTemplateCreateRequest(BaseModel):
    """Создание пользовательского logical template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ScenarioTemplateUpdateRequest(BaseModel):
    """Редактирование пользовательского logical template."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None


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


class ScenarioBundleParamPayload(BaseModel):
    """Параметр запроса внутри bundle."""
    param_name: str = Field(..., min_length=1, max_length=100)
    param_type: str = Field(..., min_length=1, max_length=50)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    string_pattern: Optional[str] = None
    string_length: Optional[int] = None
    table_ref: Optional[str] = None
    column_ref: Optional[str] = None
    current_value: Optional[int] = 0
    step: Optional[int] = 1


class ScenarioBundleQueryPayload(BaseModel):
    """Запрос внутри bundle."""
    sql_template: str = Field(..., min_length=1)
    query_type: str = Field(..., min_length=1, max_length=20)
    weight: int = Field(default=1, ge=1)
    order_index: int = Field(default=0, ge=0)
    description: Optional[str] = None
    params: List[ScenarioBundleParamPayload] = Field(default_factory=list)


class ScenarioBundleIndexPayload(BaseModel):
    """Индекс внутри bundle."""
    table_name: str = Field(..., min_length=1, max_length=100)
    column_names: str = Field(..., min_length=1, max_length=500)
    index_type: str = Field(default="btree", min_length=1, max_length=50)
    index_name: Optional[str] = Field(default=None, max_length=255)
    is_unique: bool = False
    condition: Optional[str] = None
    description: Optional[str] = None


class ScenarioBundleSummaryResponse(BaseModel):
    """Bundle variant со всеми запросами и индексами."""
    id: str
    schema_profile_id: str
    schema_profile_name: Optional[str] = None
    scenario_template_id: str
    scenario_template_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    generation_source: str
    is_builtin: bool
    is_active: bool
    generated_from_connection_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    queries: List[dict] = Field(default_factory=list)
    indexes: List[dict] = Field(default_factory=list)


class ScenarioBundleSaveRequest(BaseModel):
    """Создание или обновление bundle variant."""
    scenario_template_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    generation_source: str = Field(default="manual_variant", min_length=1, max_length=50)
    generated_from_connection_id: Optional[str] = None
    is_active: bool = False
    queries: List[ScenarioBundleQueryPayload] = Field(default_factory=list)
    indexes: List[ScenarioBundleIndexPayload] = Field(default_factory=list)


class ScenarioBundleCloneRequest(BaseModel):
    """Клонирование bundle variant."""
    name: str = Field(..., min_length=1, max_length=255)


class ProfileBundleGenerateRequest(BaseModel):
    """Запрос на генерацию profile-centric bundle'ов."""
    reference_connection_id: Optional[str] = None
    scenario_template_ids: Optional[List[str]] = None


class SchemaProfileDetailResponse(SchemaProfileSummaryResponse):
    """Детальный профиль с его bundle'ами."""
    bundles: List[ScenarioBundleSummaryResponse] = Field(default_factory=list)


class ScenarioTemplateListResponse(BaseModel):
    """Список logical templates."""
    templates: List[ScenarioTemplateResponse]


class SchemaProfileListResponse(BaseModel):
    """Список schema profiles."""
    profiles: List[SchemaProfileSummaryResponse]


class SchemaProfileBundlesResponse(BaseModel):
    """Ответ генерации bundle'ов профиля."""
    profile: SchemaProfileSummaryResponse
    bundles: List[ScenarioBundleSummaryResponse]
    generated_count: int
