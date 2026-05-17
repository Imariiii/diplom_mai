"""
Unit-тесты очистки in-memory статусов асинхронных тестов.
"""
from datetime import datetime, timedelta, timezone

from backend.api.routes.test_routes import ACTIVE_TEST_TTL, prune_active_tests


def test_prune_active_tests_removes_only_expired_terminal_entries():
    """Очистка не трогает running-тесты и свежие terminal-тесты."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    old_finished_at = now - ACTIVE_TEST_TTL - timedelta(seconds=1)
    fresh_finished_at = now - timedelta(minutes=5)
    active_tests = {
        "old-completed": {
            "status": "completed",
            "finished_at": old_finished_at,
        },
        "fresh-failed": {
            "status": "failed",
            "finished_at": fresh_finished_at,
        },
        "old-running": {
            "status": "running",
            "created_at": old_finished_at,
        },
    }

    pruned = prune_active_tests(active_tests, now=now)

    assert pruned == 1
    assert "old-completed" not in active_tests
    assert "fresh-failed" in active_tests
    assert "old-running" in active_tests


def test_prune_active_tests_accepts_iso_timestamps():
    """Timestamp из JSON-совместимого представления также очищается."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    active_tests = {
        "old-failed": {
            "status": "failed",
            "finished_at": (now - ACTIVE_TEST_TTL - timedelta(seconds=1)).isoformat(),
        },
    }

    assert prune_active_tests(active_tests, now=now) == 1
    assert active_tests == {}


def test_prune_active_tests_removes_cancelled_entries():
    """Статус cancelled также считается terminal и чистится по TTL."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    active_tests = {
        "old-cancelled": {
            "status": "cancelled",
            "finished_at": (now - ACTIVE_TEST_TTL - timedelta(seconds=1)).isoformat(),
        },
    }

    assert prune_active_tests(active_tests, now=now) == 1
    assert active_tests == {}
