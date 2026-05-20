"""
Pydantic схемы для запросов тестирования
"""
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import List, Optional


MAX_TEST_ITERATIONS = 10_000
MAX_TEST_NAME_LENGTH = 255
MAX_TEST_VIRTUAL_USERS = 100
MAX_TEST_WARMUP_TIME = 300


def build_default_test_run_name(now: Optional[datetime] = None) -> str:
    """Сгенерировать читаемое имя прогона по умолчанию."""
    moment = now or datetime.now()
    return f"Тест {moment.strftime('%d.%m.%Y %H:%M')}"


class BaseTestRequest(BaseModel):
    """Базовая схема запуска теста с ограничениями дипломного стенда"""

    query_id: Optional[str] = None
    custom_sql: Optional[str] = None
    db_types: Optional[List[str]] = None
    connection_ids: Optional[List[str]] = None
    bundle_id: Optional[str] = None
    iterations: int = 10
    virtual_users: int = 10
    scenario: Optional[str] = "mixed_light"
    use_indexes: Optional[bool] = False
    warmup_time: int = 5
    test_name: Optional[str] = None
    database_group_id: Optional[str] = None

    @field_validator("iterations")
    @classmethod
    def validate_iterations(cls, v: int) -> int:
        """Проверить количество итераций теста."""
        if v < 1:
            raise ValueError("iterations должен быть не меньше 1")
        if v > MAX_TEST_ITERATIONS:
            raise ValueError(f"iterations не может превышать {MAX_TEST_ITERATIONS}")
        return v

    @field_validator("virtual_users")
    @classmethod
    def validate_virtual_users(cls, v: int) -> int:
        """Проверить количество виртуальных пользователей."""
        if v < 1:
            raise ValueError("virtual_users должен быть не меньше 1")
        if v > MAX_TEST_VIRTUAL_USERS:
            raise ValueError(f"virtual_users не может превышать {MAX_TEST_VIRTUAL_USERS}")
        return v

    @field_validator("warmup_time")
    @classmethod
    def validate_warmup_time(cls, v: int) -> int:
        """Проверить длительность прогрева."""
        if v < 0:
            raise ValueError("warmup_time не может быть отрицательным")
        if v > MAX_TEST_WARMUP_TIME:
            raise ValueError(f"warmup_time не может превышать {MAX_TEST_WARMUP_TIME} секунд")
        return v

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

    @field_validator("test_name")
    @classmethod
    def validate_test_name(cls, v: Optional[str]) -> Optional[str]:
        """Нормализовать название прогона: пустое → None, иначе trim и проверка длины."""
        if v is None:
            return None
        name = v.strip()
        if not name:
            return None
        if len(name) > MAX_TEST_NAME_LENGTH:
            raise ValueError(
                f"test_name не может превышать {MAX_TEST_NAME_LENGTH} символов"
            )
        return name


class TestRequest(BaseTestRequest):
    """Запрос на запуск теста"""


class AsyncTestRequest(BaseTestRequest):
    """Запрос на асинхронный запуск теста"""