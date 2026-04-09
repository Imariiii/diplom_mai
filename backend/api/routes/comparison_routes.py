"""
API роуты для сравнительного анализа тестов
"""
from fastapi import APIRouter, HTTPException

from backend.comparison import ComparisonRequest, ComparisonService

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def get_repositories():
    """Получить репозитории"""
    from backend.initialize import (
        HISTORY_ENABLED,
        test_repository,
        scenario_repository,
        connection_repository,
    )

    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")

    return test_repository, scenario_repository, connection_repository


@router.post("/analyze")
async def analyze_comparison(request: ComparisonRequest):
    """Выполнить сравнительный анализ выбранных тестов"""
    test_repo, scenario_repo, connection_repo = get_repositories()
    service = ComparisonService(test_repo, scenario_repo, connection_repo)

    try:
        result = await service.analyze(request.test_ids, request.baseline_id, request.report_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        print(f"[COMPARISON] Ошибка анализа: {exc}")
        raise HTTPException(status_code=500, detail="Не удалось выполнить сравнительный анализ")

    return result
