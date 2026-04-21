"""
Pydantic схемы для запросов тестирования
"""
from pydantic import BaseModel, field_validator
from typing import List, Optional


class TestRequest(BaseModel):
    """Запрос на запуск теста"""
    query_id: Optional[str] = None
    custom_sql: Optional[str] = None
    db_types: Optional[List[str]] = None
    connection_ids: Optional[List[str]] = None
    bundle_id: Optional[str] = None
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    use_indexes: Optional[bool] = False
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None
    logical_database_id: Optional[str] = None


class AsyncTestRequest(BaseModel):
    """Запрос на асинхронный запуск теста"""
    query_id: Optional[str] = None
    custom_sql: Optional[str] = None
    db_types: Optional[List[str]] = None
    connection_ids: Optional[List[str]] = None
    bundle_id: Optional[str] = None
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    use_indexes: Optional[bool] = False
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None
    logical_database_id: Optional[str] = None

    @field_validator("custom_sql")
    @classmethod
    def validate_custom_sql(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        sql = v.strip()
        if not sql:
            return None
        if len(sql) > 10_000:
            raise ValueError("SQL-запрос не может превышать 10 000 символов")
        return sql