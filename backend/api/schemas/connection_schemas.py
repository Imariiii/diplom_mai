"""
Pydantic схемы для управления подключениями к БД
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ConnectionCreateRequest(BaseModel):
    """Запрос на создание нового подключения"""
    name: str = Field(..., min_length=1, max_length=255, description="Уникальное имя подключения")
    dbms_type: str = Field(..., description="Тип СУБД: mysql, mariadb или postgresql")
    host: str = Field(..., min_length=1, max_length=255, description="Хост базы данных")
    port: int = Field(..., ge=1, le=65535, description="Порт подключения")
    user: str = Field(..., min_length=1, max_length=100, description="Пользователь")
    password: str = Field(..., min_length=1, description="Пароль (в открытом виде, будет зашифрован)")
    database: str = Field(..., min_length=1, max_length=100, description="Имя базы данных")
    group: Optional[str] = Field(default='default', max_length=100, description="Группа подключений")
    logical_database_id: Optional[str] = Field(default=None, description="ID логической базы данных")
    extra_params: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные параметры подключения")


class ConnectionUpdateRequest(BaseModel):
    """Запрос на обновление подключения (все поля опциональны)"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    dbms_type: Optional[str] = Field(default=None)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    user: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=1)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    group: Optional[str] = Field(default=None, max_length=100)
    logical_database_id: Optional[str] = Field(default=None, description="ID логической базы данных")
    is_active: Optional[bool] = Field(default=None)
    extra_params: Optional[Dict[str, Any]] = Field(default=None)


class ConnectionResponse(BaseModel):
    """Ответ с информацией о подключении (без пароля)"""
    id: str
    name: str
    dbms_type: str
    host: str
    port: int
    user: str
    database: str
    group: Optional[str] = None
    logical_database_id: Optional[str] = None
    logical_database_name: Optional[str] = None
    schema_profile_id: Optional[str] = None
    schema_profile_name: Optional[str] = None
    detected_profile_name: Optional[str] = None
    profile_confidence: Optional[float] = None
    profile_source: Optional[str] = None
    is_active: bool
    extra_params: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConnectionTestRequest(BaseModel):
    """Запрос на тестирование подключения"""
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)
    user: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1, max_length=100)
    dbms_type: str = Field(..., description="Тип СУБД: mysql, mariadb или postgresql")
    extra_params: Optional[Dict[str, Any]] = Field(default=None)


class ConnectionTestResponse(BaseModel):
    """Результат тестирования подключения"""
    success: bool
    message: str
    response_time_ms: Optional[float] = None


class ConnectionListResponse(BaseModel):
    """Список подключений с группировкой"""
    connections: list[ConnectionResponse]
    groups: list[str]


class ConnectionGroupsResponse(BaseModel):
    """Список групп подключений"""
    groups: list[str]


class SchemaColumnResponse(BaseModel):
    """Колонка в preview схемы."""
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_unique: bool
    column_default: Optional[str] = None
    category: str


class SchemaForeignKeyResponse(BaseModel):
    """Связь foreign key в preview схемы."""
    constraint_name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class SchemaTableResponse(BaseModel):
    """Информация по таблице в preview схемы."""
    name: str
    columns: list[SchemaColumnResponse]
    primary_key: list[str]
    row_count: int
    foreign_keys_out: list[SchemaForeignKeyResponse]
    foreign_keys_in: list[SchemaForeignKeyResponse]
    unique_columns: list[str]
    capabilities: list[str]


class SchemaProfileSummaryResponse(BaseModel):
    """Краткая информация о профиле данных."""
    id: str
    name: str
    description: Optional[str] = None
    detection_mode: Optional[str] = None
    reference_connection_id: Optional[str] = None
    is_builtin: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SchemaProfileSuggestionResponse(BaseModel):
    """Автоматически предложенный профиль схемы."""
    name: str
    description: str
    confidence: float
    reason: str
    existing_profile_id: Optional[str] = None
    is_existing: bool = False


class ConnectionSchemaResponse(BaseModel):
    """Preview схемы подключённой БД."""
    connection_id: str
    connection_name: str
    dbms_type: str
    total_tables: int
    tables: list[SchemaTableResponse]
    current_profile: Optional[SchemaProfileSummaryResponse] = None
    suggested_profile: Optional[SchemaProfileSuggestionResponse] = None
    available_scenario_types: list[str] = []
    matching_templates: Dict[str, list[str]] = {}
