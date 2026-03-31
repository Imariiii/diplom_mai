"""
API роуты для выполнения тестов
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from typing import Dict, List
import uuid
import asyncio

from backend.api.schemas import AsyncTestRequest
from backend.load_tester.tester import LoadTester
from backend.websocket_manager import manager, TestStreamingCallback

router = APIRouter(prefix="/test", tags=["test"])


def get_active_tests():
    """Получить хранилище активных тестов из main.py"""
    from backend.main import active_tests
    return active_tests


@router.post("/async")
async def run_async_test(request: AsyncTestRequest, background_tasks: BackgroundTasks):
    """
    Асинхронный запуск теста с WebSocket обновлениями.
    Возвращает test_id для подписки на обновления.
    """
    from backend.initialize import HISTORY_ENABLED, test_repository
    
    test_id = str(uuid.uuid4())
    test_name = request.test_name or f"Тест {test_id}"
    
    active_tests = get_active_tests()
    
    # Сохраняем информацию о тесте
    active_tests[test_id] = {
        "id": test_id,
        "name": test_name,
        "status": "pending",
        "config": request.model_dump(),
    }
    
    # Создаём запись в БД истории (если включена)
    if HISTORY_ENABLED and test_repository:
        try:
            from datetime import datetime, timezone
            test_repository.create_test_run(
                name=test_name,
                config=request.model_dump(),
                status='pending',
                test_run_id=test_id
            )
        except Exception as e:
            print(f"[HISTORY_DB] ❌ Ошибка создания записи в БД истории: {e}")
    
    # Запускаем тест в фоне
    background_tasks.add_task(
        run_test_with_streaming,
        test_id,
        request
    )
    
    return {
        "test_id": test_id,
        "name": test_name,
        "status": "pending",
        "websocket_url": f"/ws/test/{test_id}",
        "message": "Тест запущен. Подключитесь к WebSocket для получения обновлений."
    }


async def run_test_with_streaming(test_id: str, request: AsyncTestRequest):
    """Фоновая задача для выполнения теста с WebSocket стримингом"""
    from datetime import datetime, timedelta, timezone
    import time
    
    from backend.initialize import (
        HISTORY_ENABLED, 
        test_repository, 
        scenario_repository,
    )
    
    # Используем get_active_tests() для правильного импорта
    active_tests = get_active_tests()
    
    start_ts = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    # Создаём callback для streaming
    streaming_callback = TestStreamingCallback(test_id, manager)
    
    # Создаём новый экземпляр тестера для этого теста
    test_tester = LoadTester()
    test_tester.set_streaming_callback(streaming_callback)
    
    try:
        # Обновляем статус
        active_tests[test_id]["status"] = "running"
        await streaming_callback.on_test_start()
        
        # Определяем тип сценария: строковый (старый) или UUID (новый из БД)
        scenario = request.scenario or "mixed_light"
        is_scenario_uuid = False
        
        # Проверяем, является ли scenario UUID (новый формат из БД)
        try:
            uuid.UUID(scenario)
            is_scenario_uuid = True
        except (ValueError, TypeError):
            is_scenario_uuid = False
        
        if is_scenario_uuid:
            # Запускаем тест по сценарию из БД
            results = await test_tester.run_full_scenario_test_suite(
                scenario_id=scenario,
                db_types=request.db_types,
                iterations=request.iterations,
                virtual_users=request.virtual_users,
                warmup_time=request.warmup_time,
                scenario_repository=scenario_repository
            )
        else:
            # Запускаем тест по старому строковому сценарию
            results = await test_tester.run_full_test_suite(
                db_types=request.db_types,
                iterations=request.iterations,
                virtual_users=request.virtual_users,
                scenario=scenario,
                warmup_time=request.warmup_time
            )
        
        end_time = time.perf_counter()
        actual_duration = end_time - start_time
        finish_ts = start_ts + timedelta(seconds=actual_duration)

        # Собираем системные и СУБД метрики
        system_metrics = {}
        dbms_metrics = {}
        for db_type in request.db_types:
            try:
                system_metrics[db_type] = await test_tester.get_system_metrics(db_type)
                dbms_metrics[db_type] = await test_tester.get_dbms_metrics(db_type)
            except Exception as e:
                print(f"Ошибка сбора метрик для {db_type}: {e}")

        # Вычисляем итоговую статистику
        total_transactions = 0
        for result in results:
            if 'comparison' in result:
                for db_type, stats in result.get('comparison', {}).items():
                    total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
            elif 'stats' in result:
                total_transactions += result['stats'].get('successful', 0) + result['stats'].get('failed', 0)
        
        summary = {
            'total_transactions': total_transactions,
            'overall_tps': total_transactions / actual_duration if actual_duration > 0 else 0,
            'total_duration': actual_duration
        }
        
        # Сохраняем в БД истории
        if HISTORY_ENABLED and test_repository:
            try:
                test_repository.update_test_run_status(
                    test_id,
                    'completed',
                    summary,
                    started_at=start_ts,
                    finished_at=finish_ts
                )
                
                for result in results:
                    if 'comparison' in result:
                        for db_type, stats in result.get('comparison', {}).items():
                            test_repository.add_test_result(
                                test_run_id=test_id,
                                db_type=db_type,
                                metrics=stats,
                                query_id=result.get('query_id'),
                                system_metrics=system_metrics.get(db_type),
                                dbms_metrics=dbms_metrics.get(db_type)
                            )
                    elif 'stats' in result and 'db_type' in result:
                        db_type = result['db_type']
                        stats = result['stats']
                        scenario_name = result.get('scenario', 'unknown')
                        test_repository.add_test_result(
                            test_run_id=test_id,
                            db_type=db_type,
                            metrics=stats,
                            query_id=f"scenario:{scenario_name}",
                            system_metrics=system_metrics.get(db_type),
                            dbms_metrics=dbms_metrics.get(db_type)
                        )
            except Exception as e:
                print(f"[HISTORY_DB] ❌ Ошибка сохранения в БД истории: {e}")
        
        # Обновляем локальное состояние
        active_tests[test_id]["status"] = "completed"
        active_tests[test_id]["results"] = results
        active_tests[test_id]["summary"] = summary
        active_tests[test_id]["system_metrics"] = system_metrics
        active_tests[test_id]["dbms_metrics"] = dbms_metrics
        
        # Уведомляем через WebSocket
        await streaming_callback.on_test_complete(summary)
        
    except Exception as e:
        print(f"Ошибка выполнения теста {test_id}: {e}")
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = str(e)
        
        await streaming_callback.on_test_error(str(e))
        
        if HISTORY_ENABLED and test_repository:
            try:
                finish_ts = start_ts + timedelta(seconds=(time.perf_counter() - start_time))
                test_repository.update_test_run_status(
                    test_id,
                    'failed',
                    None,
                    started_at=start_ts,
                    finished_at=finish_ts
                )
            except:
                pass
    finally:
        test_tester.close()


@router.get("/async/{test_id}")
async def get_async_test_status(test_id: str):
    """Получить статус асинхронного теста"""
    active_tests = get_active_tests()
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    return active_tests[test_id]


@router.get("/async/{test_id}/results")
async def get_async_test_results(test_id: str):
    """Получить результаты асинхронного теста"""
    active_tests = get_active_tests()
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    test_info = active_tests[test_id]
    if test_info["status"] != "completed":
        return {
            "status": test_info["status"],
            "message": "Тест ещё не завершён"
        }
    
    return {
        "status": "completed",
        "results": test_info.get("results", []),
        "summary": test_info.get("summary", {}),
        "system_metrics": test_info.get("system_metrics", {}),
        "dbms_metrics": test_info.get("dbms_metrics", {})
    }