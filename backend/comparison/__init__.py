"""
Модуль сравнительного анализа результатов нагрузочного тестирования
"""
from backend.comparison.schemas import (
    AnalysisMode,
    ComparisonRequest,
    ComparisonResult,
    PerTestResult,
    SeriesResult,
)


def __getattr__(name):
    """Ленивая загрузка сервиса для предотвращения циклических импортов"""
    if name == "ComparisonService":
        from backend.comparison.service import ComparisonService
        return ComparisonService
    raise AttributeError(name)

__all__ = [
    "AnalysisMode",
    "ComparisonRequest",
    "ComparisonResult",
    "ComparisonService",
    "PerTestResult",
    "SeriesResult",
]
