"""
Unit-тесты ограничений параметров запуска нагрузочного теста.
"""
import pytest
from pydantic import ValidationError

from backend.api.schemas.test_schemas import AsyncTestRequest, TestRequest


@pytest.mark.parametrize("schema_cls", [TestRequest, AsyncTestRequest])
def test_load_test_request_accepts_safe_defaults(schema_cls):
    """Дефолтные параметры соответствуют безопасному дипломному стенду."""
    request = schema_cls()

    assert request.iterations == 10
    assert request.virtual_users == 10
    assert request.warmup_time == 5


@pytest.mark.parametrize("schema_cls", [TestRequest, AsyncTestRequest])
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("iterations", 0, "iterations должен быть не меньше 1"),
        ("iterations", 10_001, "iterations не может превышать 10000"),
        ("virtual_users", 0, "virtual_users должен быть не меньше 1"),
        ("virtual_users", 101, "virtual_users не может превышать 100"),
        ("warmup_time", -1, "warmup_time не может быть отрицательным"),
        ("warmup_time", 301, "warmup_time не может превышать 300 секунд"),
    ],
)
def test_load_test_request_rejects_unsafe_limits(schema_cls, field, value, message):
    """Опасные параметры отклоняются до постановки теста в фон."""
    with pytest.raises(ValidationError) as exc_info:
        schema_cls(**{field: value})

    assert message in str(exc_info.value)


@pytest.mark.parametrize("schema_cls", [TestRequest, AsyncTestRequest])
def test_load_test_request_accepts_boundary_values(schema_cls):
    """Граничные допустимые значения остаются валидными."""
    request = schema_cls(
        iterations=10_000,
        virtual_users=100,
        warmup_time=300,
    )

    assert request.iterations == 10_000
    assert request.virtual_users == 100
    assert request.warmup_time == 300
