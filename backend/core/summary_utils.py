"""
Утилиты для нормализации summary тестового прогона.
"""
from typing import Any, Dict, Optional


def sanitize_test_summary(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Убрать устаревшие поля из summary перед отдачей клиенту."""
    if not summary:
        return summary
    cleaned = dict(summary)
    cleaned.pop("overall_tps", None)
    return cleaned
