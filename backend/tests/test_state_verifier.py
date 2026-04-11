"""
Unit-тесты для backend/database/state_verifier.py
Проверка верификации состояния БД через fingerprint-сравнение.
"""
from datetime import datetime, timezone

import pytest

from backend.database.state_verifier import (
    StateFingerprint,
    TableFingerprint,
    VerifyResult,
    StateVerifier,
)


def _make_fingerprint(tables_spec: dict) -> StateFingerprint:
    """Создать StateFingerprint из словаря {table_name: row_count}"""
    fp = StateFingerprint(timestamp=datetime.now(timezone.utc))
    for name, row_count in tables_spec.items():
        fp.tables[name] = TableFingerprint(table_name=name, row_count=row_count)
    return fp


# =========================================================================
# VerifyResult
# =========================================================================

class TestVerifyResult:
    def test_add_matching_table(self):
        vr = VerifyResult(success=True)
        vr.add_table_result("film", 100, 100)
        assert vr.details["film"]["match"] is True
        assert len(vr.errors) == 0

    def test_add_mismatched_table(self):
        vr = VerifyResult(success=True)
        vr.add_table_result("film", 100, 95)
        assert vr.details["film"]["match"] is False
        assert len(vr.errors) == 1
        assert "film" in vr.errors[0]

    def test_checksum_match(self):
        vr = VerifyResult(success=True)
        vr.add_table_result("film", 100, 100, "abc123", "abc123")
        assert vr.details["film"]["match"] is True

    def test_checksum_mismatch(self):
        vr = VerifyResult(success=True)
        vr.add_table_result("film", 100, 100, "abc123", "xyz789")
        assert vr.details["film"]["match"] is False

    def test_to_dict(self):
        vr = VerifyResult(success=True, errors=["err1"])
        d = vr.to_dict()
        assert d["success"] is True
        assert d["errors"] == ["err1"]


# =========================================================================
# StateFingerprint
# =========================================================================

class TestStateFingerprint:
    def test_to_dict(self):
        fp = _make_fingerprint({"film": 100, "actor": 50})
        d = fp.to_dict()
        assert "film" in d["tables"]
        assert d["tables"]["film"]["row_count"] == 100

    def test_empty(self):
        fp = StateFingerprint(timestamp=datetime.now(timezone.utc))
        assert len(fp.tables) == 0


# =========================================================================
# StateVerifier.verify
# =========================================================================

class TestStateVerifierVerify:
    @pytest.fixture
    def verifier(self):
        return StateVerifier()

    @pytest.mark.asyncio
    async def test_identical_fingerprints(self, verifier):
        before = _make_fingerprint({"film": 100, "actor": 50})
        after = _make_fingerprint({"film": 100, "actor": 50})
        result = await verifier.verify(before, after)
        assert result.success is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_different_row_counts(self, verifier):
        before = _make_fingerprint({"film": 100})
        after = _make_fingerprint({"film": 95})
        result = await verifier.verify(before, after)
        assert result.success is False
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_missing_table_in_after(self, verifier):
        before = _make_fingerprint({"film": 100, "actor": 50})
        after = _make_fingerprint({"film": 100})
        result = await verifier.verify(before, after)
        assert result.success is False
        assert any("missing" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_extra_table_in_after(self, verifier):
        before = _make_fingerprint({"film": 100})
        after = _make_fingerprint({"film": 100, "extra": 10})
        result = await verifier.verify(before, after)
        assert result.success is False
        assert any("unexpected" in e.lower() or "Unexpected" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_empty_fingerprints(self, verifier):
        before = _make_fingerprint({})
        after = _make_fingerprint({})
        result = await verifier.verify(before, after)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_mismatches(self, verifier):
        before = _make_fingerprint({"film": 100, "actor": 50, "rental": 200})
        after = _make_fingerprint({"film": 95, "actor": 45, "rental": 200})
        result = await verifier.verify(before, after)
        assert result.success is False
        assert len(result.errors) == 2
