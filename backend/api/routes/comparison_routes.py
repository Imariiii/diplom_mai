"""
API роуты для сравнительного анализа тестов
"""
from fastapi import APIRouter, HTTPException

from backend.comparison import ComparisonRequest, ComparisonService

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


def get_test_repository():
    """Получить репозиторий тестов"""
    from backend.initialize import HISTORY_ENABLED, test_repository

    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")

    return test_repository


@router.post("/analyze")
async def analyze_comparison(request: ComparisonRequest):
    """Выполнить сравнительный анализ выбранных тестов"""
    repo = get_test_repository()
    service = ComparisonService(repo)

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
