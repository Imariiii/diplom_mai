"""
API роуты для истории тестирования
"""
from fastapi import APIRouter, HTTPException, Query
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
async def get_history_tests(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    logical_database_id: Optional[str] = Query(None),
):
    """Получить историю тестов из БД"""
    repo = get_test_repository()
    tests = await repo.get_all_test_runs(
        limit=limit,
        offset=offset,
        status=status,
        logical_database_id=logical_database_id,
    )
    total = await repo.count_test_runs(
        status=status,
        logical_database_id=logical_database_id,
    )
    return {"tests": tests, "total": total}


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


@router.get("/tests/{test_id}/time-series")
async def get_history_test_time_series(
    test_id: str,
    db_type: Optional[str] = Query(None, description="Фильтр по типу СУБД"),
    limit: Optional[int] = Query(500, ge=1, le=10000, description="Максимальное количество точек на СУБД"),
    full: bool = Query(False, description="Вернуть полный временной ряд без ограничения"),
):
    """Получить временные ряды метрик теста для построения графиков"""
    repo = get_test_repository()
    test = await repo.get_test_run(test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    points = await repo.get_time_series(
        test_id,
        db_type=db_type,
        limit=None if full else limit,
    )
    return {"test_id": test_id, "points": points, "count": len(points)}


@router.get("/tests/{test_id}/errors")
async def get_history_test_errors(
    test_id: str,
    db_type: Optional[str] = Query(None, description="Фильтр по типу СУБД"),
    limit: int = Query(100, le=1000, description="Максимальное количество примеров ошибок"),
):
    """Получить сгруппированные ошибки запросов для теста."""
    repo = get_test_repository()
    test = await repo.get_test_run(test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    return await repo.get_test_error_report(test_id, db_type=db_type, limit=limit)


@router.delete("/tests/{test_id}")
async def delete_history_test(test_id: str):
    """Удалить тест из истории"""
    repo = get_test_repository()
    deleted = await repo.delete_test_run(test_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    return {"deleted": True, "test_id": test_id}
