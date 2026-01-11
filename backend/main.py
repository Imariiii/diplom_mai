"""
Backend API для системы нагрузочного тестирования
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
import asyncio
import uuid
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_tester.tester import LoadTester
from visualizer.charts import ResultVisualizer
from visualizer.result_saver import ResultSaver
from database.connection import DatabaseConnection
from database.queries import QueryManager
from backend.websocket_manager import manager, TestStreamingCallback

app = FastAPI(title="Database Load Testing API", version="2.0.0")

# Определяем project_root здесь, до использования
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Опционально: подключение к БД истории (если настроена)
def get_history_db_url():
    """Получить URL для базы данных истории"""
    # Сначала проверяем переменную окружения
    env_url = os.getenv('HISTORY_DATABASE_URL')
    if env_url:
        return env_url
    
    # Пробуем использовать конфиг PostgreSQL из database_config.yaml
    try:
        import yaml
        config_path = os.path.join(project_root, "config", "database_config.yaml")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            pg = config.get('databases', {}).get('postgresql', {})
            if pg:
                host = pg.get('host', 'localhost')
                port = pg.get('port', 5432)
                user = pg.get('user', 'postgres')
                password = pg.get('password', '')
                # Используем отдельную БД для истории
                db = 'test_history'
                return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    except Exception as e:
        print(f"⚠️ Не удалось загрузить конфиг: {e}")
    
    return None

try:
    from database.repository import TestRepository
    HISTORY_DB_URL = get_history_db_url()
    if HISTORY_DB_URL:
        test_repository = TestRepository(HISTORY_DB_URL)
        HISTORY_ENABLED = True
        print(f"✅ История тестов включена")
    else:
        test_repository = None
        HISTORY_ENABLED = False
        print("ℹ️ История тестов отключена (не настроен HISTORY_DATABASE_URL)")
except Exception as e:
    print(f"⚠️ История тестов отключена: {e}")
    test_repository = None
    HISTORY_ENABLED = False

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
    duration: Optional[int] = 60           # Длительность теста в секундах
    virtual_users: Optional[int] = 10      # Количество виртуальных пользователей
    scenario: Optional[str] = "mixed_light" # Сценарий тестирования
    warmup_time: Optional[int] = 5         # Время прогрева в секундах


class TestResult(BaseModel):
    query_id: str
    comparison: Dict
    timestamp: str


class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage_mb: float
    memory_usage_percent: float
    disk_iops: float
    network_in_mbps: float
    network_out_mbps: float


class DBMSMetrics(BaseModel):
    cache_hit_ratio: float
    buffer_pool_hit_ratio: float
    lock_waits: int
    deadlocks: int
    active_connections: int
    table_sizes_mb: Dict[str, float]
    index_sizes_mb: Dict[str, float]
    total_db_size_mb: float


# Определяем директорию results относительно корня проекта
results_dir = os.path.join(project_root, "results")

# Инициализация компонентов
tester = LoadTester()
visualizer = ResultVisualizer(output_dir=os.path.join(results_dir, "charts"))
result_saver = ResultSaver(output_dir=results_dir)
db_connection = DatabaseConnection()
query_manager = QueryManager()

# Хранилище активных тестов (для WebSocket)
active_tests: Dict[str, Dict] = {}


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "Database Load Testing API",
        "version": "1.0.0"
    }


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


@app.post("/test/single", response_model=TestResult)
async def run_single_test(request: TestRequest):
    """Запуск теста для одного запроса"""
    try:
        if request.query_id is None:
            queries = query_manager.get_all_queries()
            if not queries:
                raise HTTPException(status_code=400, detail="Нет доступных запросов")
            request.query_id = queries[0]['id']
        
        result = await tester.run_comparison_test(
            request.query_id,
            request.db_types,
            request.iterations,
            virtual_users=request.virtual_users,
            scenario=request.scenario
        )
        
        return TestResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/full")
async def run_full_test(request: TestRequest):
    """Запуск полного набора тестов с сохранением результатов"""
    try:
        # Генерируем ID теста
        test_id = result_saver.generate_test_id()
        
        # Конфигурация для сохранения
        config = {
            'db_types': request.db_types,
            'iterations': request.iterations,
            'duration': request.duration,
            'virtual_users': request.virtual_users,
            'scenario': request.scenario,
            'warmup_time': request.warmup_time
        }
        
        # Запуск тестов
        results = await tester.run_full_test_suite(
            request.db_types,
            request.iterations,
            duration=request.duration,
            virtual_users=request.virtual_users,
            scenario=request.scenario,
            warmup_time=request.warmup_time
        )
        
        # Сбор системных и СУБД метрик
        system_metrics = {}
        dbms_metrics = {}
        for db_type in request.db_types:
            try:
                system_metrics[db_type] = await tester.get_system_metrics(db_type)
                dbms_metrics[db_type] = await tester.get_dbms_metrics(db_type)
            except Exception as e:
                print(f"Ошибка сбора метрик для {db_type}: {e}")
        
        # Сохранение результатов
        saved_files = result_saver.save_full_test_results(
            test_id=test_id,
            config=config,
            results=results,
            system_metrics=system_metrics,
            dbms_metrics=dbms_metrics
        )
        
        # Создание визуализаций
        comparison_chart = visualizer.create_comparison_chart(results)
        statistics_chart = visualizer.create_statistics_chart(results)
        report = visualizer.create_summary_report(results)
        
        # Подсчет общей статистики
        total_transactions = 0
        total_duration = request.duration or 60
        
        for result in results:
            for db_type, stats in result.get('comparison', {}).items():
                total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
        
        return {
            "test_id": test_id,
            "results": results,
            "system_metrics": system_metrics,
            "dbms_metrics": dbms_metrics,
            "charts": {
                "comparison": comparison_chart,
                "statistics": statistics_chart,
                "report": report
            },
            "saved_files": saved_files,
            "summary": {
                "total_duration": total_duration,
                "total_transactions": total_transactions,
                "overall_tps": total_transactions / total_duration if total_duration > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/charts")
async def get_charts():
    """Получить список созданных графиков"""
    charts_dir = os.path.join(results_dir, "charts")
    charts = []
    
    if os.path.exists(charts_dir):
        for filename in os.listdir(charts_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                charts.append({
                    "filename": filename,
                    "path": os.path.join(charts_dir, filename)
                })
    
    return {"charts": charts}


@app.get("/results/tests")
async def get_all_tests():
    """Получить список всех сохраненных тестов"""
    tests = result_saver.list_all_tests()
    return {"tests": tests}


@app.get("/results/tests/{test_id}")
async def get_test_results(test_id: str):
    """Получить результаты конкретного теста"""
    results = result_saver.load_test_results(test_id)
    if results is None:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    return results


@app.get("/results/tests/{test_id}/report")
async def get_test_report(test_id: str, format: str = "txt"):
    """Получить отчет по тесту"""
    if format == "md":
        filepath = os.path.join(results_dir, "reports", f"report_{test_id}.md")
    else:
        filepath = os.path.join(results_dir, "reports", f"report_{test_id}.txt")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Отчет для теста {test_id} не найден")
    
    return FileResponse(filepath, filename=os.path.basename(filepath))


@app.get("/results/tests/{test_id}/csv")
async def get_test_csv(test_id: str, type: str = "metrics"):
    """Получить CSV с результатами теста"""
    if type == "comparison":
        filepath = os.path.join(results_dir, "csv", f"comparison_{test_id}.csv")
    else:
        filepath = os.path.join(results_dir, "csv", f"metrics_{test_id}.csv")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"CSV для теста {test_id} не найден")
    
    return FileResponse(filepath, filename=os.path.basename(filepath))


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


@app.delete("/results/tests/{test_id}")
async def delete_test(test_id: str):
    """Удалить результаты теста"""
    deleted_files = []
    
    # Удаляем все файлы, связанные с тестом
    patterns = [
        (os.path.join(results_dir, "json"), f"test_{test_id}.json"),
        (os.path.join(results_dir, "json"), f"config_{test_id}.json"),
        (os.path.join(results_dir, "csv"), f"metrics_{test_id}.csv"),
        (os.path.join(results_dir, "csv"), f"comparison_{test_id}.csv"),
        (os.path.join(results_dir, "reports"), f"report_{test_id}.txt"),
        (os.path.join(results_dir, "reports"), f"report_{test_id}.md"),
    ]
    
    for dir_path, filename in patterns:
        filepath = os.path.join(dir_path, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted_files.append(filepath)
    
    if not deleted_files:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    return {"deleted": deleted_files}


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


@app.websocket("/ws/global")
async def websocket_global_endpoint(websocket: WebSocket):
    """
    Глобальный WebSocket endpoint для получения обновлений всех тестов.
    """
    await manager.connect(websocket, "global")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "global")
    except Exception as e:
        print(f"[WS Global] Ошибка: {e}")
        manager.disconnect(websocket, "global")


@app.get("/ws/connections")
async def get_ws_connections():
    """Получить информацию о WebSocket соединениях"""
    return {
        "total_connections": manager.get_connection_count(),
        "active_tests": list(active_tests.keys())
    }


# ==================== Real-time Test Execution ====================

class AsyncTestRequest(BaseModel):
    """Запрос на асинхронный запуск теста"""
    query_id: Optional[str] = None
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 10
    duration: Optional[int] = 60
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
    test_id = str(uuid.uuid4())[:8]
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
    if HISTORY_ENABLED and test_repository:
        try:
            test_repository.create_test_run(
                name=test_name,
                config=request.model_dump(),
                status='pending'
            )
        except Exception as e:
            print(f"Ошибка создания записи в БД истории: {e}")
    
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
    
    # Создаём callback для streaming
    streaming_callback = TestStreamingCallback(test_id, manager)
    streaming_callback.set_duration(request.duration or 60)
    
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
            duration=request.duration,
            virtual_users=request.virtual_users,
            scenario=request.scenario,
            warmup_time=request.warmup_time
        )
        
        # Сохраняем результаты
        config = {
            'db_types': request.db_types,
            'iterations': request.iterations,
            'duration': request.duration,
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
        
        # Сохраняем в файлы
        saved_files = result_saver.save_full_test_results(
            test_id=test_id,
            config=config,
            results=results,
            system_metrics=system_metrics,
            dbms_metrics=dbms_metrics
        )
        
        # Создание визуализаций
        visualizer.create_comparison_chart(results)
        visualizer.create_statistics_chart(results)
        visualizer.create_summary_report(results)
        
        # Вычисляем итоговую статистику
        total_transactions = 0
        for result in results:
            for db_type, stats in result.get('comparison', {}).items():
                total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
        
        summary = {
            'total_transactions': total_transactions,
            'overall_tps': total_transactions / (request.duration or 60),
            'total_duration': request.duration or 60
        }
        
        # Сохраняем в БД истории
        if HISTORY_ENABLED and test_repository:
            try:
                # Обновляем статус теста
                test_repository.update_test_run_status(test_id, 'completed', summary)
                
                # Сохраняем результаты по каждой СУБД
                for result in results:
                    for db_type, stats in result.get('comparison', {}).items():
                        test_repository.add_test_result(
                            test_run_id=test_id,
                            db_type=db_type,
                            metrics=stats,
                            query_id=result.get('query_id'),
                            system_metrics=system_metrics.get(db_type),
                            dbms_metrics=dbms_metrics.get(db_type)
                        )
            except Exception as e:
                print(f"Ошибка сохранения в БД истории: {e}")
        
        # Обновляем локальное состояние
        active_tests[test_id]["status"] = "completed"
        active_tests[test_id]["results"] = results
        active_tests[test_id]["summary"] = summary
        
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
        "summary": test_info.get("summary", {})
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
