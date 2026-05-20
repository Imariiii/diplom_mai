"""
Unit-тесты валидации test_name в схемах запуска теста.
"""
import pytest
from pydantic import ValidationError

from backend.api.schemas.test_schemas import (
    AsyncTestRequest,
    build_default_test_run_name,
    MAX_TEST_NAME_LENGTH,
)


class TestTestNameValidation:
    def test_empty_string_becomes_none(self):
        req = AsyncTestRequest(test_name="   ")
        assert req.test_name is None

    def test_whitespace_trimmed(self):
        req = AsyncTestRequest(test_name="  My run  ")
        assert req.test_name == "My run"

    def test_none_allowed(self):
        req = AsyncTestRequest(test_name=None)
        assert req.test_name is None

    def test_too_long_raises(self):
        with pytest.raises(ValidationError):
            AsyncTestRequest(test_name="x" * (MAX_TEST_NAME_LENGTH + 1))

    def test_max_length_ok(self):
        name = "a" * MAX_TEST_NAME_LENGTH
        req = AsyncTestRequest(test_name=name)
        assert req.test_name == name


class TestBuildDefaultTestRunName:
    def test_format(self):
        from datetime import datetime

        name = build_default_test_run_name(datetime(2026, 5, 21, 14, 30))
        assert name == "Тест 21.05.2026 14:30"
