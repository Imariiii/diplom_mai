"""
Модуль сравнительного анализа результатов нагрузочного тестирования
"""
from backend.comparison.schemas import ComparisonRequest, ComparisonResult


def __getattr__(name):
    """Ленивая загрузка сервиса для предотвращения циклических импортов"""
    if name == "ComparisonService":
        from backend.comparison.service import ComparisonService
        return ComparisonService
    raise AttributeError(name)

__all__ = [
    "ComparisonRequest",
    "ComparisonResult",
    "ComparisonService",
]
