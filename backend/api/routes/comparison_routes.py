"""
API роуты для двухрежимного сравнительного анализа прогонов
"""
from fastapi import APIRouter, HTTPException

from backend.comparison.schemas import (
    AnalysisMode,
    ComparisonRequest,
    ComparisonResult,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def get_repositories():
    """Получить репозитории"""
    from backend.initialize import (
        HISTORY_ENABLED,
        test_repository,
        scenario_bundle_repository,
        connection_repository,
    )

    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")

    return test_repository, scenario_bundle_repository, connection_repository


@router.post("/analyze")
async def analyze_comparison(request: ComparisonRequest) -> ComparisonResult:
    """Выполнить сравнительный анализ прогонов.

    Два режима:
    - per_test: один прогон, сравнение СУБД на одной нагрузке
    - series: серия прогонов, анализ траекторий СУБД при разных нагрузках
    """
    from backend.comparison.service import ComparisonService

    test_repo, bundle_repo, connection_repo = get_repositories()
    service = ComparisonService(test_repo, bundle_repo, connection_repo)

    try:
        result = await service.analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        print(f"[COMPARISON] Ошибка анализа: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Не удалось выполнить сравнительный анализ",
        )

    return result
