"""
Pydantic схемы для запросов тестирования
"""
from pydantic import BaseModel
from typing import List, Optional


class TestRequest(BaseModel):
    """Запрос на запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = None  # ["mysql", "postgresql"] - для обратной совместимости
    connection_ids: Optional[List[str]] = None  # ID подключений из БД
    bundle_id: Optional[str] = None
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    use_indexes: Optional[bool] = False
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None
    logical_database_id: Optional[str] = None  # ID логической базы данных


class AsyncTestRequest(BaseModel):
    """Запрос на асинхронный запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = None  # ["mysql", "postgresql"] - для обратной совместимости
    connection_ids: Optional[List[str]] = None  # ID подключений из БД
    bundle_id: Optional[str] = None
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    use_indexes: Optional[bool] = False
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None
    logical_database_id: Optional[str] = None  # ID логической базы данных