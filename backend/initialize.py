"""
Инициализация глобальных компонентов приложения
"""
import os
import sys

# Пути
# Для initialize.py: файл находится в backend/initialize.py, поэтому нужно подняться на 2 уровня
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Глобальные переменные для репозиториев
test_repository = None
scenario_repository = None
HISTORY_ENABLED = False
SCENARIOS_ENABLED = False


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


def initialize_repositories():
    """Инициализировать репозитории"""
    global test_repository, scenario_repository, HISTORY_ENABLED, SCENARIOS_ENABLED
    
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

    print("[SCENARIO_REPO] Инициализация ScenarioRepository...")
    try:
        from backend.database.repository import ScenarioRepository
        history_db_url = get_history_db_url()
        scenario_repository = ScenarioRepository(history_db_url) if history_db_url else None
        SCENARIOS_ENABLED = HISTORY_ENABLED and scenario_repository is not None
        print(f"[SCENARIO_REPO] ✅ Сценарии инициализированы: SCENARIOS_ENABLED = {SCENARIOS_ENABLED}")
    except Exception as e:
        print(f"[SCENARIO_REPO] ❌ Ошибка инициализации: {e}")
        scenario_repository = None
        SCENARIOS_ENABLED = False


# Инициализация при импорте модуля (вызывается явно из main.py)
def init():
    """Явная инициализация репозиториев - вызвать из main.py"""
    initialize_repositories()
    return test_repository, scenario_repository