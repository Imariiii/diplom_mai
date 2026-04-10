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
