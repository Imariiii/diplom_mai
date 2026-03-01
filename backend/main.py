"""
Backend API для системы нагрузочного тестирования
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
import asyncio
import uuid
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.load_tester.tester import LoadTester
from backend.database.connection import DatabaseConnection
from backend.database.queries import QueryManager
from backend.websocket_manager import manager, TestStreamingCallback

app = FastAPI(title="Database Load Testing API", version="2.0.0")

# Определяем пути относительно расположения файлов
backend_root = os.path.dirname(os.path.abspath(__file__))

def get_history_db_url():
    """Получить URL для базы данных истории из конфига"""
    print("[HISTORY_DB] Попытка настройки подключения к БД истории...")
    
    env_url = os.getenv('HISTORY_DATABASE_URL')
    if env_url:
        print(f"[HISTORY_DB] Используется HISTORY_DATABASE_URL из окружения")
        return env_url
    
    try:
        import yaml
        config_path = os.path.join(backend_root, "config", "database_config.yaml")
        print(f"[HISTORY_DB] Чтение конфига: {config_path}")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            history_config = config.get('databases', {}).get('test_history', {})
            print(f"[HISTORY_DB] Конфиг test_history найден: {bool(history_config)}")
            
            if history_config:
                host = history_config.get('host', 'localhost')
                port = history_config.get('port', 5433)
                user = history_config.get('user', 'postgres')
                password = history_config.get('password', '')
                database = history_config.get('database', 'test_history')
                
                print(f"[HISTORY_DB] Подключение к: {host}:{port}/{database}")
                return f"postgresql://{user}:{password}@{host}:{port}/{database}"
            else:
                print("[HISTORY_DB] ❌ Секция 'test_history' не найдена в конфиге")
        else:
            print(f"[HISTORY_DB] ❌ Конфиг файл не найден: {config_path}")
    except Exception as e:
        print(f"[HISTORY_DB] ❌ Ошибка чтения конфига: {e}")
        import traceback
        traceback.print_exc()
    
    return None

print("[HISTORY_DB] === ИНИЦИАЛИЗАЦИЯ БД ИСТОРИИ ===")
try:
    from backend.database.repository import TestRepository
    HISTORY_DB_URL = get_history_db_url()
    print(f"[HISTORY_DB] URL получен: {HISTORY_DB_URL is not None}")
    
    if HISTORY_DB_URL:
        print(f"[HISTORY_DB] Создание TestRepository...")
        test_repository = TestRepository(HISTORY_DB_URL)
        HISTORY_ENABLED = True
        print(f"[HISTORY_DB] ✅ История тестов включена успешно")
        print(f"[HISTORY_DB] HISTORY_ENABLED = {HISTORY_ENABLED}")
    else:
        test_repository = None
        HISTORY_ENABLED = False
        print("[HISTORY_DB] ℹ️ История тестов отключена (URL не сформирован)")
except Exception as e:
    print(f"[HISTORY_DB] ❌ История тестов отключена из-за ошибки: {e}")
    import traceback
    traceback.print_exc()
    test_repository = None
    HISTORY_ENABLED = False
print(f"[HISTORY_DB] === ИТОГ: HISTORY_ENABLED = {HISTORY_ENABLED} ===")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Типы сценариев тестирования
TestScenario = Literal[
    "read_only",      # 100% SELECT
    "write_only",     # 100% INSERT/UPDATE/DELETE
    "mixed_light",    # 80% SELECT, 20% UPDATE
    "mixed_heavy",    # 50% SELECT, 50% UPDATE
    "oltp",           # OLTP-подобная нагрузка
    "olap",           # OLAP-подобная нагрузка
    "custom"          # Пользовательский сценарий
]


# Модели данных
class TestRequest(BaseModel):
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10
    virtual_users: Optional[int] = 10      # Количество виртуальных пользователей
    scenario: Optional[str] = "mixed_light" # Сценарий тестирования
    warmup_time: Optional[int] = 5         # Время прогрева в секундах
    test_name: Optional[str] = None        # Название теста


# Инициализация компонентов
tester = LoadTester()
db_connection = DatabaseConnection()
query_manager = QueryManager()

# Хранилище активных тестов (для WebSocket)
active_tests: Dict[str, Dict] = {}


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    mysql_status = db_connection.test_connection("mysql")
    postgres_status = db_connection.test_connection("postgresql")
    
    return {
        "status": "ok",
        "mysql": "connected" if mysql_status else "disconnected",
        "postgresql": "connected" if postgres_status else "disconnected"
    }


@app.get("/queries")
async def get_queries():
    """Получить список всех доступных запросов"""
    return query_manager.get_all_queries()


@app.get("/queries/{query_id}")
async def get_query(query_id: str):
    """Получить конкретный запрос"""
    try:
        return query_manager.get_query(query_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/metrics/system/{db_type}")
async def get_system_metrics(db_type: str):
    """Получить системные метрики для СУБД"""
    try:
        metrics = await tester.get_system_metrics(db_type)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/dbms/{db_type}")
async def get_dbms_metrics(db_type: str):
    """Получить внутренние метрики СУБД"""
    try:
        metrics = await tester.get_dbms_metrics(db_type)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket Endpoints ====================

@app.websocket("/ws/test/{test_id}")
async def websocket_test_endpoint(websocket: WebSocket, test_id: str):
    """
    WebSocket endpoint для подписки на обновления конкретного теста.
    Отправляет метрики в реальном времени во время выполнения теста.
    """
    await manager.connect(websocket, test_id)
    try:
        while True:
            # Ожидаем сообщения от клиента (ping/pong или команды)
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "subscribe":
                # Дополнительная подписка на другой тест
                new_test_id = data.get("test_id")
                if new_test_id:
                    await manager.connect(websocket, new_test_id)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, test_id)
    except Exception as e:
        print(f"[WS] Ошибка: {e}")
        manager.disconnect(websocket, test_id)


# ==================== Real-time Test Execution ====================

class AsyncTestRequest(BaseModel):
    """Запрос на асинхронный запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10
    virtual_users: Optional[int] = 10
    scenario: Optional[str] = "mixed_light"
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None


@app.post("/test/async")
async def run_async_test(request: AsyncTestRequest, background_tasks: BackgroundTasks):
    """
    Асинхронный запуск теста с WebSocket обновлениями.
    Возвращает test_id для подписки на обновления.
    """
    test_id = str(uuid.uuid4())
    test_name = request.test_name or f"Тест {test_id}"
    
    # Сохраняем информацию о тесте
    active_tests[test_id] = {
        "id": test_id,
        "name": test_name,
        "status": "pending",
        "config": request.model_dump(),
        "created_at": asyncio.get_event_loop().time()
    }
    
    # Создаём запись в БД истории (если включена)
    print(f"[HISTORY_DB] Проверка при создании теста: HISTORY_ENABLED={HISTORY_ENABLED}, test_repository={test_repository is not None}")
    if HISTORY_ENABLED and test_repository:
        print(f"[HISTORY_DB] Создание записи TestRun для теста {test_id}...")
        try:
            test_repository.create_test_run(
                name=test_name,
                config=request.model_dump(),
                status='pending',
                test_run_id=test_id
            )
            print(f"[HISTORY_DB] ✅ Запись TestRun создана для теста {test_id}")
        except Exception as e:
            print(f"[HISTORY_DB] ❌ Ошибка создания записи в БД истории: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[HISTORY_DB] ⚠️ Создание записи в БД истории пропущено")
    
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
    import time
    start_time = time.time()
    
    # Создаём callback для streaming
    streaming_callback = TestStreamingCallback(test_id, manager)
    
    # Создаём новый экземпляр тестера для этого теста
    test_tester = LoadTester()
    test_tester.set_streaming_callback(streaming_callback)
    
    try:
        # Обновляем статус
        active_tests[test_id]["status"] = "running"
        await streaming_callback.on_test_start()
        
        # Запускаем тесты
        results = await test_tester.run_full_test_suite(
            db_types=request.db_types,
            iterations=request.iterations,
            virtual_users=request.virtual_users,
            scenario=request.scenario,
            warmup_time=request.warmup_time
        )
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Сохраняем результаты
        config = {
            'db_types': request.db_types,
            'iterations': request.iterations,
            'virtual_users': request.virtual_users,
            'scenario': request.scenario,
            'warmup_time': request.warmup_time
        }
        
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
            for db_type, stats in result.get('comparison', {}).items():
                total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
        
        summary = {
            'total_transactions': total_transactions,
            'overall_tps': total_transactions / actual_duration if actual_duration > 0 else 0,
            'total_duration': actual_duration
        }
        
        # Сохраняем в БД истории
        print(f"[HISTORY_DB] Проверка перед сохранением: HISTORY_ENABLED={HISTORY_ENABLED}, test_repository={test_repository is not None}")
        if HISTORY_ENABLED and test_repository:
            print(f"[HISTORY_DB] Начинаем сохранение результатов теста {test_id}...")
            try:
                # Обновляем статус теста
                print(f"[HISTORY_DB] Обновление статуса теста {test_id} на 'completed'...")
                test_repository.update_test_run_status(test_id, 'completed', summary)
                print(f"[HISTORY_DB] Статус обновлён")
                
                # Сохраняем результаты по каждой СУБД
                print(f"[HISTORY_DB] Сохранение результатов по СУБД (всего результатов: {len(results)})...")
                for result in results:
                    for db_type, stats in result.get('comparison', {}).items():
                        print(f"[HISTORY_DB] Сохранение результата для {db_type}, query={result.get('query_id')}")
                        test_repository.add_test_result(
                            test_run_id=test_id,
                            db_type=db_type,
                            metrics=stats,
                            query_id=result.get('query_id'),
                            system_metrics=system_metrics.get(db_type),
                            dbms_metrics=dbms_metrics.get(db_type)
                        )
                print(f"[HISTORY_DB] ✅ Результаты теста {test_id} успешно сохранены в БД истории")
            except Exception as e:
                print(f"[HISTORY_DB] ❌ Ошибка сохранения в БД истории: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[HISTORY_DB] ⚠️ Сохранение в БД истории пропущено: HISTORY_ENABLED={HISTORY_ENABLED}")
        
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
                test_repository.update_test_run_status(test_id, 'failed')
            except:
                pass
    finally:
        test_tester.close()


@app.get("/test/async/{test_id}")
async def get_async_test_status(test_id: str):
    """Получить статус асинхронного теста"""
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    return active_tests[test_id]


@app.get("/test/async/{test_id}/results")
async def get_async_test_results(test_id: str):
    """Получить результаты асинхронного теста"""
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


# ==================== History Endpoints ====================

@app.get("/history/enabled")
async def history_status():
    """Проверить, включена ли история тестов"""
    return {"enabled": HISTORY_ENABLED}


@app.get("/history/tests")
async def get_history_tests(limit: int = 50, offset: int = 0, status: Optional[str] = None):
    """Получить историю тестов из БД"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        tests = test_repository.get_all_test_runs(limit=limit, offset=offset, status=status)
        return {"tests": tests, "total": len(tests)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/tests/{test_id}")
async def get_history_test(test_id: str):
    """Получить тест из истории по ID"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        test = test_repository.get_test_run_with_results(test_id)
        if not test:
            raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
        return test
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/tests/{test_id}/timeseries")
async def get_history_timeseries(test_id: str, db_type: Optional[str] = None, limit: int = 1000):
    """Получить временной ряд теста"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        timeseries = test_repository.get_time_series(test_id, db_type=db_type, limit=limit)
        return {"timeseries": timeseries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/compare/{test_id_1}/{test_id_2}")
async def compare_history_tests(test_id_1: str, test_id_2: str):
    """Сравнить два теста из истории"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        comparison = test_repository.compare_test_runs(test_id_1, test_id_2)
        if not comparison:
            raise HTTPException(status_code=404, detail="Один или оба теста не найдены")
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/history/tests/{test_id}")
async def delete_history_test(test_id: str):
    """Удалить тест из истории"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        deleted = test_repository.delete_test_run(test_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
        return {"deleted": True, "test_id": test_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/statistics")
async def get_history_statistics():
    """Получить статистику по истории тестов"""
    if not HISTORY_ENABLED or not test_repository:
        raise HTTPException(status_code=503, detail="История тестов не настроена")
    
    try:
        stats = test_repository.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
