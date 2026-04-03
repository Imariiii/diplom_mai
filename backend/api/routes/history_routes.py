"""
API роуты для истории тестирования
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter(prefix="/history", tags=["history"])


def get_test_repository():
    """Получить репозиторий тестов"""
    from backend.initialize import HISTORY_ENABLED, test_repository
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    return test_repository


@router.get("/enabled")
async def history_status():
    """Проверить, включена ли история тестов"""
    from backend.initialize import HISTORY_ENABLED
    return {"enabled": HISTORY_ENABLED}


@router.get("/tests")
async def get_history_tests(limit: int = 50, offset: int = 0, status: Optional[str] = None):
    """Получить историю тестов из БД"""
    repo = get_test_repository()
    tests = await repo.get_all_test_runs(limit=limit, offset=offset, status=status)
    return {"tests": tests, "total": len(tests)}


@router.get("/tests/{test_id}")
async def get_history_test(test_id: str):
    """Получить тест из истории по ID"""
    repo = get_test_repository()
    test = await repo.get_test_run_with_results(test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    return test


@router.get("/compare/{test_id_1}/{test_id_2}")
async def compare_history_tests(test_id_1: str, test_id_2: str):
    """Сравнить два теста из истории"""
    repo = get_test_repository()
    comparison = await repo.compare_test_runs(test_id_1, test_id_2)
    if not comparison:
        raise HTTPException(status_code=404, detail="Один или оба теста не найдены")
    return comparison


@router.delete("/tests/{test_id}")
async def delete_history_test(test_id: str):
    """Удалить тест из истории"""
    repo = get_test_repository()
    deleted = await repo.delete_test_run(test_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    return {"deleted": True, "test_id": test_id}
