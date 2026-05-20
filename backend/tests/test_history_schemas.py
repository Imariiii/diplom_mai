"""
Unit-тесты схем истории тестов.
"""
import pytest
from pydantic import ValidationError

from backend.api.schemas.history_schemas import RenameTestRunRequest


class TestRenameTestRunRequest:
    def test_valid_name(self):
        req = RenameTestRunRequest(name="  My test  ")
        assert req.name == "My test"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            RenameTestRunRequest(name="   ")
