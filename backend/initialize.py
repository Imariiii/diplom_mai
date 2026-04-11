"""
Инициализация глобальных компонентов приложения
"""
import os
import sys

from backend.core.config import settings

# Пути
# Для initialize.py: файл находится в backend/initialize.py, поэтому нужно подняться на 2 уровня
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Глобальные переменные для репозиториев
test_repository = None
connection_repository = None
profile_repository = None
scenario_bundle_repository = None
logical_database_repository = None
HISTORY_ENABLED = False


def get_history_db_url():
    """Получить URL для базы данных истории из .env"""
    print("[HISTORY_DB] Попытка настройки подключения к БД истории...")
    if settings.history_db_url:
        print("[HISTORY_DB] Используется HISTORY_DATABASE_URL из .env")
        return settings.history_db_url
    print("[HISTORY_DB] HISTORY_DATABASE_URL не задан")
    return None


def initialize_repositories():
    """Инициализировать репозитории"""
    global test_repository
    global connection_repository
    global profile_repository
    global scenario_bundle_repository
    global logical_database_repository
    global HISTORY_ENABLED

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

    print("[CONNECTION_REPO] Инициализация ConnectionRepository...")
    try:
        from backend.database.repository import ConnectionRepository
        history_db_url = get_history_db_url()
        if history_db_url:
            connection_repository = ConnectionRepository(history_db_url)
            print(f"[CONNECTION_REPO] ✅ ConnectionRepository инициализирован")
        else:
            connection_repository = None
            print(f"[CONNECTION_REPO] ⚠️ ConnectionRepository не инициализирован (нет URL)")
    except Exception as e:
        print(f"[CONNECTION_REPO] ❌ Ошибка инициализации: {e}")
        connection_repository = None

    print("[PROFILE_REPO] Инициализация ProfileRepository...")
    try:
        from backend.database.repository import ProfileRepository
        history_db_url = get_history_db_url()
        if history_db_url:
            profile_repository = ProfileRepository(history_db_url)
            print("[PROFILE_REPO] ✅ ProfileRepository инициализирован")
        else:
            profile_repository = None
            print("[PROFILE_REPO] ⚠️ ProfileRepository не инициализирован (нет URL)")
    except Exception as e:
        print(f"[PROFILE_REPO] ❌ Ошибка инициализации: {e}")
        profile_repository = None

    print("[BUNDLE_REPO] Инициализация ScenarioBundleRepository...")
    try:
        from backend.database.repository import ScenarioBundleRepository
        history_db_url = get_history_db_url()
        if history_db_url:
            scenario_bundle_repository = ScenarioBundleRepository(history_db_url)
            print("[BUNDLE_REPO] ✅ ScenarioBundleRepository инициализирован")
        else:
            scenario_bundle_repository = None
            print("[BUNDLE_REPO] ⚠️ ScenarioBundleRepository не инициализирован (нет URL)")
    except Exception as e:
        print(f"[BUNDLE_REPO] ❌ Ошибка инициализации: {e}")
        scenario_bundle_repository = None

    print("[LOGICAL_DB_REPO] Инициализация LogicalDatabaseRepository...")
    try:
        from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
        history_db_url = get_history_db_url()
        if history_db_url:
            logical_database_repository = LogicalDatabaseRepository(history_db_url)
            print("[LOGICAL_DB_REPO] ✅ LogicalDatabaseRepository инициализирован")
        else:
            logical_database_repository = None
            print("[LOGICAL_DB_REPO] ⚠️ LogicalDatabaseRepository не инициализирован (нет URL)")
    except Exception as e:
        print(f"[LOGICAL_DB_REPO] ❌ Ошибка инициализации: {e}")
        logical_database_repository = None


# Инициализация при импорте модуля (вызывается явно из main.py)
def init():
    """Явная инициализация репозиториев - вызвать из main.py"""
    initialize_repositories()
    return test_repository, scenario_bundle_repository
