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


# ==================== Модели для сценариев тестирования ====================

class ScenarioParamCreate(BaseModel):
    param_name: str
    param_type: str  # random_int, random_string, random_date, sequential_int, uuid, random_from_table
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    string_pattern: Optional[str] = None
    string_length: Optional[int] = None
    table_ref: Optional[str] = None
    column_ref: Optional[str] = None
    current_value: int = 0
    step: int = 1


class ScenarioParamUpdate(BaseModel):
    param_name: Optional[str] = None
    param_type: Optional[str] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    string_pattern: Optional[str] = None
    string_length: Optional[int] = None
    table_ref: Optional[str] = None
    column_ref: Optional[str] = None
    current_value: Optional[int] = None
    step: Optional[int] = None


class ScenarioParamResponse(BaseModel):
    id: str
    query_id: str
    param_name: str
    param_type: str
    min_value: Optional[int]
    max_value: Optional[int]
    string_pattern: Optional[str]
    string_length: Optional[int]
    table_ref: Optional[str]
    column_ref: Optional[str]
    current_value: Optional[int]
    step: Optional[int]
    created_at: str


class ScenarioQueryCreate(BaseModel):
    sql_template: str
    query_type: str  # select, insert, update, delete
    weight: int = 1
    order_index: int = 0
    description: Optional[str] = None
    params: List[ScenarioParamCreate] = []


class ScenarioQueryUpdate(BaseModel):
    sql_template: Optional[str] = None
    query_type: Optional[str] = None
    weight: Optional[int] = None
    order_index: Optional[int] = None
    description: Optional[str] = None


class ScenarioQueryResponse(BaseModel):
    id: str
    scenario_id: str
    sql_template: str
    query_type: str
    weight: int
    order_index: int
    description: Optional[str]
    created_at: str
    params: List[ScenarioParamResponse]


class TestScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scenario_type: str  # read_only, write_only, mixed_light, mixed_heavy, oltp, olap, custom
    queries: List[ScenarioQueryCreate] = []


class TestScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scenario_type: Optional[str] = None
    is_active: Optional[bool] = None


class TestScenarioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    scenario_type: str
    is_builtin: bool
    is_active: bool
    created_at: str
    updated_at: str
    queries: List[ScenarioQueryResponse]


class TestScenarioListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    scenario_type: str
    is_builtin: bool
    is_active: bool
    created_at: str


class CloneScenarioRequest(BaseModel):
    new_name: str


# Инициализация компонентов
print("[SCENARIO_REPO] Инициализация ScenarioRepository...")
try:
    from backend.database.repository import ScenarioRepository
    scenario_repository = ScenarioRepository(HISTORY_DB_URL) if HISTORY_DB_URL else None
    SCENARIOS_ENABLED = HISTORY_ENABLED and scenario_repository is not None
    print(f"[SCENARIO_REPO] ✅ Сценарии инициализированы: SCENARIOS_ENABLED = {SCENARIOS_ENABLED}")
except Exception as e:
    print(f"[SCENARIO_REPO] ❌ Ошибка инициализации: {e}")
    scenario_repository = None
    SCENARIOS_ENABLED = False


# Инициализация компонентов тестирования
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
    import uuid
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
            print(f"[TEST] Запуск теста по сценарию из БД: {scenario}")
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
            print(f"[TEST] Запуск теста по сценарию: {scenario}")
            results = await test_tester.run_full_test_suite(
                db_types=request.db_types,
                iterations=request.iterations,
                virtual_users=request.virtual_users,
                scenario=scenario,
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
        
        # Вычисляем итоговую статистику (поддержка обоих форматов результатов)
        total_transactions = 0
        for result in results:
            # Старый формат: {'comparison': {db_type: stats, ...}}
            if 'comparison' in result:
                for db_type, stats in result.get('comparison', {}).items():
                    total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
            # Новый формат: {'db_type': ..., 'stats': stats}
            elif 'stats' in result:
                total_transactions += result['stats'].get('successful', 0) + result['stats'].get('failed', 0)
        
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
                
                # Сохраняем результаты по каждой СУБД (поддержка обоих форматов)
                print(f"[HISTORY_DB] Сохранение результатов по СУБД (всего результатов: {len(results)})...")
                for result in results:
                    # Старый формат
                    if 'comparison' in result:
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
                    # Новый формат
                    elif 'stats' in result and 'db_type' in result:
                        db_type = result['db_type']
                        stats = result['stats']
                        scenario_name = result.get('scenario', 'unknown')
                        print(f"[HISTORY_DB] Сохранение результата для {db_type}, scenario={scenario_name}")
                        test_repository.add_test_result(
                            test_run_id=test_id,
                            db_type=db_type,
                            metrics=stats,
                            query_id=f"scenario:{scenario_name}",
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


# ==================== Scenario Endpoints ====================

@app.get("/scenarios/enabled")
async def scenarios_enabled():
    """Проверить, включена ли функциональность сценариев"""
    return {"enabled": SCENARIOS_ENABLED}


@app.get("/scenarios")
async def get_scenarios(
    limit: int = 100,
    offset: int = 0,
    scenario_type: Optional[str] = None,
    include_builtin: bool = True
):
    """Получить список всех сценариев тестирования"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenarios = scenario_repository.get_all_scenarios(
            limit=limit,
            offset=offset,
            scenario_type=scenario_type,
            include_builtin=include_builtin
        )
        return {"scenarios": scenarios, "total": len(scenarios)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Получить сценарий по ID с запросами и параметрами"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")
        return scenario.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios")
async def create_scenario(request: TestScenarioCreate):
    """Создать новый сценарий тестирования"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        # Проверяем уникальность имени
        existing = scenario_repository.get_scenario_by_name(request.name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.name}' уже существует")

        # Создаём сценарий
        scenario = scenario_repository.create_scenario(
            name=request.name,
            description=request.description,
            scenario_type=request.scenario_type,
            is_builtin=False
        )

        # Добавляем запросы к сценарию
        for idx, query_data in enumerate(request.queries):
            query = scenario_repository.add_query_to_scenario(
                scenario_id=str(scenario.id),
                sql_template=query_data.sql_template,
                query_type=query_data.query_type,
                weight=query_data.weight,
                order_index=query_data.order_index if query_data.order_index else idx,
                description=query_data.description
            )

            # Добавляем параметры к запросу
            for param_data in query_data.params:
                scenario_repository.add_param_to_query(
                    query_id=str(query.id),
                    param_name=param_data.param_name,
                    param_type=param_data.param_type,
                    min_value=param_data.min_value,
                    max_value=param_data.max_value,
                    string_pattern=param_data.string_pattern,
                    string_length=param_data.string_length,
                    table_ref=param_data.table_ref,
                    column_ref=param_data.column_ref,
                    current_value=param_data.current_value,
                    step=param_data.step
                )

        # Возвращаем созданный сценарий
        return scenario_repository.get_scenario(str(scenario.id)).to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, request: TestScenarioUpdate):
    """Обновить сценарий тестирования"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        # Проверяем существование
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии (кроме is_active)
        if scenario.is_builtin == 't' and (request.name or request.description or request.scenario_type):
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        # Проверяем уникальность имени
        if request.name and request.name != scenario.name:
            existing = scenario_repository.get_scenario_by_name(request.name)
            if existing:
                raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.name}' уже существует")

        updated = scenario_repository.update_scenario(
            scenario_id=scenario_id,
            name=request.name,
            description=request.description,
            scenario_type=request.scenario_type,
            is_active=request.is_active
        )

        return updated.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """Удалить сценарий тестирования"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        # Проверяем существование
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Удаляем
        deleted = scenario_repository.delete_scenario(scenario_id)
        if not deleted:
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя удалить")

        return {"deleted": True, "scenario_id": scenario_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios/{scenario_id}/clone")
async def clone_scenario(scenario_id: str, request: CloneScenarioRequest):
    """Клонировать сценарий тестирования"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        # Проверяем существование оригинала
        original = scenario_repository.get_scenario(scenario_id)
        if not original:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Проверяем уникальность нового имени
        existing = scenario_repository.get_scenario_by_name(request.new_name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.new_name}' уже существует")

        cloned = scenario_repository.clone_scenario(scenario_id, request.new_name)
        return cloned.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scenario Query Endpoints ====================

@app.get("/scenarios/{scenario_id}/queries")
async def get_scenario_queries(scenario_id: str):
    """Получить все запросы сценария"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        queries = [q.to_dict() for q in scenario.queries]
        return {"queries": queries}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios/{scenario_id}/queries")
async def add_query_to_scenario(scenario_id: str, request: ScenarioQueryCreate):
    """Добавить запрос к сценарию"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        # Добавляем запрос
        query = scenario_repository.add_query_to_scenario(
            scenario_id=scenario_id,
            sql_template=request.sql_template,
            query_type=request.query_type,
            weight=request.weight,
            order_index=request.order_index,
            description=request.description
        )

        # Добавляем параметры
        for param_data in request.params:
            scenario_repository.add_param_to_query(
                query_id=str(query.id),
                param_name=param_data.param_name,
                param_type=param_data.param_type,
                min_value=param_data.min_value,
                max_value=param_data.max_value,
                string_pattern=param_data.string_pattern,
                string_length=param_data.string_length,
                table_ref=param_data.table_ref,
                column_ref=param_data.column_ref,
                current_value=param_data.current_value,
                step=param_data.step
            )

        return scenario_repository.get_query(str(query.id)).to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/scenarios/{scenario_id}/queries/{query_id}")
async def update_scenario_query(scenario_id: str, query_id: str, request: ScenarioQueryUpdate):
    """Обновить запрос сценария"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        updated = scenario_repository.update_query(
            query_id=query_id,
            sql_template=request.sql_template,
            query_type=request.query_type,
            weight=request.weight,
            order_index=request.order_index,
            description=request.description
        )

        return updated.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scenarios/{scenario_id}/queries/{query_id}")
async def delete_scenario_query(scenario_id: str, query_id: str):
    """Удалить запрос из сценария"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        scenario_repository.delete_query(query_id)
        return {"deleted": True, "query_id": query_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scenario Param Endpoints ====================

@app.get("/scenarios/{scenario_id}/queries/{query_id}/params")
async def get_query_params(scenario_id: str, query_id: str):
    """Получить все параметры запроса"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        params = [p.to_dict() for p in query.params]
        return {"params": params}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scenarios/{scenario_id}/queries/{query_id}/params")
async def add_param_to_query(scenario_id: str, query_id: str, request: ScenarioParamCreate):
    """Добавить параметр к запросу"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        param = scenario_repository.add_param_to_query(
            query_id=query_id,
            param_name=request.param_name,
            param_type=request.param_type,
            min_value=request.min_value,
            max_value=request.max_value,
            string_pattern=request.string_pattern,
            string_length=request.string_length,
            table_ref=request.table_ref,
            column_ref=request.column_ref,
            current_value=request.current_value,
            step=request.step
        )

        return param.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/scenarios/{scenario_id}/queries/{query_id}/params/{param_id}")
async def update_query_param(
    scenario_id: str,
    query_id: str,
    param_id: str,
    request: ScenarioParamUpdate
):
    """Обновить параметр запроса"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        param = scenario_repository.get_param(param_id)
        if not param or str(param.query_id) != query_id:
            raise HTTPException(status_code=404, detail=f"Параметр {param_id} не найден в запросе {query_id}")

        updated = scenario_repository.update_param(
            param_id=param_id,
            param_name=request.param_name,
            param_type=request.param_type,
            min_value=request.min_value,
            max_value=request.max_value,
            string_pattern=request.string_pattern,
            string_length=request.string_length,
            table_ref=request.table_ref,
            column_ref=request.column_ref,
            current_value=request.current_value,
            step=request.step
        )

        return updated.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scenarios/{scenario_id}/queries/{query_id}/params/{param_id}")
async def delete_query_param(scenario_id: str, query_id: str, param_id: str):
    """Удалить параметр запроса"""
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")

    try:
        scenario = scenario_repository.get_scenario(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

        # Нельзя редактировать built-in сценарии
        if scenario.is_builtin == 't':
            raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

        query = scenario_repository.get_query(query_id)
        if not query or str(query.scenario_id) != scenario_id:
            raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

        param = scenario_repository.get_param(param_id)
        if not param or str(param.query_id) != query_id:
            raise HTTPException(status_code=404, detail=f"Параметр {param_id} не найден в запросе {query_id}")

        scenario_repository.delete_param(param_id)
        return {"deleted": True, "param_id": param_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scenario-based Testing Endpoints ====================

class ScenarioTestRequest(BaseModel):
    scenario_id: str
    db_types: Optional[List[str]] = ["mysql", "postgresql"]
    iterations: int = 100
    virtual_users: Optional[int] = 10
    warmup_time: Optional[int] = 5
    test_name: Optional[str] = None


@app.post("/test/scenario")
async def run_scenario_test_endpoint(
    request: ScenarioTestRequest,
    background_tasks: BackgroundTasks
):
    """
    Запуск нагрузочного теста на основе сценария из БД.
    
    В отличие от старого метода, использует параметризованные SQL-запросы
    из сценария с динамической подстановкой значений.
    """
    if not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")
    
    try:
        import time
        start_time = time.time()
        
        # Проверяем, что сценарий существует
        scenario = scenario_repository.get_scenario(request.scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Сценарий {request.scenario_id} не найден")
        
        # Генерируем ID теста
        test_id = result_saver.generate_test_id() if 'result_saver' in globals() else str(uuid.uuid4())[:8]
        
        # Конфигурация для сохранения
        config = {
            'scenario_id': request.scenario_id,
            'scenario_name': scenario['name'],
            'scenario_type': scenario['scenario_type'],
            'db_types': request.db_types,
            'iterations': request.iterations,
            'virtual_users': request.virtual_users,
            'warmup_time': request.warmup_time
        }
        
        # Устанавливаем callbacks для WebSocket
        if manager:
            callback = TestStreamingCallback(test_id, manager)
            callback.set_total_queries(len(request.db_types))
            tester.set_streaming_callback(callback)
        
        # Запуск теста
        results = await tester.run_full_scenario_test_suite(
            scenario_id=request.scenario_id,
            db_types=request.db_types,
            iterations=request.iterations,
            virtual_users=request.virtual_users,
            warmup_time=request.warmup_time
        )
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Собираем системные метрики
        system_metrics = {}
        dbms_metrics = {}
        for db_type in request.db_types:
            try:
                system_metrics[db_type] = await tester.get_system_metrics(db_type)
                dbms_metrics[db_type] = await tester.get_dbms_metrics(db_type)
            except Exception as e:
                print(f"Ошибка сбора метрик для {db_type}: {e}")
        
        # Подсчет общей статистики
        total_transactions = 0
        for result in results:
            stats = result.get('stats', {})
            total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
        
        summary = {
            'total_transactions': total_transactions,
            'overall_tps': total_transactions / actual_duration if actual_duration > 0 else 0,
            'total_duration': actual_duration
        }
        
        # Сохраняем в БД истории
        if HISTORY_ENABLED and test_repository:
            try:
                test_name = request.test_name or f"Сценарий: {scenario['name']}"
                test_repository.create_test_run(
                    name=test_name,
                    config=config,
                    status='completed',
                    test_run_id=test_id
                )
                test_repository.update_test_run_status(test_id, 'completed', summary)
                
                for result in results:
                    db_type = result.get('db_type')
                    stats = result.get('stats', {})
                    test_repository.add_test_result(
                        test_run_id=test_id,
                        db_type=db_type,
                        metrics=stats,
                        query_id=request.scenario_id,
                        system_metrics=system_metrics.get(db_type),
                        dbms_metrics=dbms_metrics.get(db_type)
                    )
                print(f"✅ Результаты теста {test_id} сохранены в БД истории")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в БД истории: {e}")
        
        return {
            "test_id": test_id,
            "scenario": {
                "id": request.scenario_id,
                "name": scenario['name'],
                "type": scenario['scenario_type']
            },
            "results": results,
            "system_metrics": system_metrics,
            "dbms_metrics": dbms_metrics,
            "summary": {
                "total_duration": actual_duration,
                "total_transactions": total_transactions,
                "overall_tps": total_transactions / actual_duration if actual_duration > 0 else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
