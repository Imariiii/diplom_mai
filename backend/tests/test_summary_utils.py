"""Тесты нормализации summary тестового прогона."""
from backend.core.summary_utils import sanitize_test_summary


def test_sanitize_test_summary_removes_overall_tps():
    summary = {
        "total_transactions": 1500,
        "overall_tps": 12.12,
        "total_duration": 124.0,
    }
    cleaned = sanitize_test_summary(summary)
    assert cleaned == {
        "total_transactions": 1500,
        "total_duration": 124.0,
    }


def test_sanitize_test_summary_handles_empty():
    assert sanitize_test_summary(None) is None
    assert sanitize_test_summary({}) == {}
