"""
Backend API для системы нагрузочного тестирования
Точка входа FastAPI приложения
"""
from contextlib import asynccontextmanager
from typing import Dict
import sys
import os
from dotenv import load_dotenv

# Загружаем .env из корневой директории
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.load_tester.tester import LoadTester
from backend.database.connection import DatabaseConnection
from backend.websocket_manager import manager, TestStreamingCallback
from backend.database.state_manager import DatabaseStateManager

# Импорт роутов из api модуля
from backend.api.routes import test_routes, database_state_routes, history_routes, settings_routes, connection_routes, comparison_routes, profile_routes
from backend.api.routes import database_group_routes

# Используем централизованную инициализацию
from backend import initialize


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск миграций Alembic при старте приложения."""
    from backend.core.config import settings as app_settings
    db_url = app_settings.database.history_db_url
    if db_url:
        print("[STARTUP] Запуск миграций Alembic...")
        try:
            from alembic.config import Config as AlembicConfig
            from alembic import command as alembic_command

            alembic_cfg = AlembicConfig()
            alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "migrations"))
            alembic_cfg.set_main_option("sqlalchemy.url", db_url.replace("+asyncpg", "+psycopg2"))
            alembic_command.upgrade(alembic_cfg, "head")
            print("[STARTUP] Миграции Alembic применены")

            if initialize.connection_repository and initialize.profile_repository and initialize.scenario_bundle_repository:
                from backend.database.logical_scenario_bootstrap import LogicalScenarioBootstrap

                bootstrap = LogicalScenarioBootstrap(
                    connection_repository=initialize.connection_repository,
                    profile_repository=initialize.profile_repository,
                    bundle_repository=initialize.scenario_bundle_repository,
                    database_group_repository=initialize.database_group_repository,
                )
                await bootstrap.bootstrap()
                print("[STARTUP] Logical scenario bootstrap завершён")
        except Exception as e:
            print(f"[STARTUP] ⚠ Миграции завершились с ошибкой: {e}")
            import traceback
            traceback.print_exc()
            raise
    else:
        print("[STARTUP] HISTORY_DATABASE_URL не задан, миграции пропущены")
    yield


app = FastAPI(title="Database Load Testing API", version="2.0.0", lifespan=lifespan)

# Инициализация менеджеров состояния БД (lazy - при первом использовании)
db_state_manager: DatabaseStateManager = None
db_connection_instance: DatabaseConnection = None


def get_db_state_manager() -> DatabaseStateManager:
    """Получить менеджер состояния БД"""
    global db_state_manager
    if db_state_manager is None:
        db_state_manager = DatabaseStateManager()
    return db_state_manager


def get_db_connection() -> DatabaseConnection:
    """Получить подключение к БД"""
    global db_connection_instance
    if db_connection_instance is None:
        db_connection_instance = DatabaseConnection()
        db_connection_instance.set_connection_repository(initialize.connection_repository)
    return db_connection_instance


# Явная инициализация репозиториев
initialize.init()
test_repository = initialize.test_repository
connection_repository = initialize.connection_repository
profile_repository = initialize.profile_repository
scenario_bundle_repository = initialize.scenario_bundle_repository
HISTORY_ENABLED = initialize.HISTORY_ENABLED

print(f"[INIT] HISTORY_ENABLED = {HISTORY_ENABLED}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Инициализация компонентов тестирования
tester = LoadTester(connection_repo=initialize.connection_repository)
db_connection = get_db_connection()

# Хранилище активных тестов (для WebSocket)
active_tests: Dict[str, Dict] = {}


# ==================== Основные endpoints ====================

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    history_status = "connected" if HISTORY_ENABLED else "disconnected"

    return {
        "status": "ok",
        "api": "connected",
        "history_db": history_status,
    }


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


# ==================== Подключение роутов ====================

# Тестовые роуты
app.include_router(test_routes.router)

# Роуты состояния БД
app.include_router(database_state_routes.router)

# Роуты истории
app.include_router(history_routes.router)

# Роуты настроек
app.include_router(settings_routes.router)

# Роуты управления подключениями
app.include_router(connection_routes.router)

# Роуты профилей схемы и logical templates
app.include_router(profile_routes.router)

# Роуты сравнительного анализа
app.include_router(comparison_routes.router)

# Роуты групп баз данных
app.include_router(database_group_routes.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
