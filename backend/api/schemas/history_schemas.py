"""
Pydantic-схемы для API истории тестов
"""
from pydantic import BaseModel, Field, field_validator

from backend.api.schemas.test_schemas import MAX_TEST_NAME_LENGTH


class RenameTestRunRequest(BaseModel):
    """Запрос на переименование прогона в истории"""

    name: str = Field(..., min_length=1, max_length=MAX_TEST_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Обрезать пробелы; пустое имя недопустимо."""
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("name не может быть пустым")
        return trimmed
