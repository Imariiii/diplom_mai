"""
Pydantic схемы для запросов тестирования
"""
from pydantic import BaseModel
from typing import List, Optional, Literal

TestScenario = Literal[
    "read_only",      # 100% SELECT
    "write_only",     # 100% INSERT/UPDATE/DELETE
    "mixed_light",    # 80% SELECT, 20% UPDATE
    "mixed_heavy",    # 50% SELECT, 50% UPDATE
    "oltp",           # OLTP-подобная нагрузка
    "olap",           # OLAP-подобная нагрузка
    "custom"          # Пользовательский сценарий
]


class TestRequest(BaseModel):
    """Запрос на запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10
    virtual_users: Optional[int] = 10      # Количество виртуальных пользователей
    scenario: Optional[str] = "mixed_light" # Сценарий тестирования
    warmup_time: Optional[int] = 5         # Время прогрева в секундах
    test_name: Optional[str] = None        # Название теста


class AsyncTestRequest(BaseModel):
    """Запрос на асинхронный запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None