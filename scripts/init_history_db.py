#!/usr/bin/env python3
"""
Скрипт инициализации базы данных для истории тестов.

Варианты использования:
1. Docker (рекомендуется): docker-compose up -d history-db && python scripts/init_history_db.py --docker
2. Существующий PostgreSQL: python scripts/init_history_db.py --use-pagila-server
"""
import os
import sys
import yaml
import argparse
import subprocess

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database.models import Base

# Конфигурация для Docker контейнера
DOCKER_CONFIG = {
    'host': 'localhost',
    'port': 5433,  # Отдельный порт для истории
    'user': 'postgres',
    'password': 'history123',
    'database': 'test_history'
}


def load_database_config():
    """Загрузить конфигурацию PostgreSQL из database_config.yaml"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "database_config.yaml"
    )
    
    if not os.path.exists(config_path):
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    pg_config = config.get('databases', {}).get('postgresql', {})
    return pg_config


def build_connection_url(config: dict, database: str = None) -> str:
    """Построить URL подключения из конфига"""
    host = config.get('host', 'localhost')
    port = config.get('port', 5432)
    user = config.get('user', 'postgres')
    password = config.get('password', '')
    db = database or config.get('database', 'postgres')
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def start_docker_container() -> bool:
    """Запустить Docker контейнер с PostgreSQL для истории"""
    print("\n🐳 Запуск Docker контейнера для БД истории...")
    
    try:
        # Проверяем, запущен ли уже контейнер
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=test_history_db"],
            capture_output=True, text=True
        )
        
        if result.stdout.strip():
            print("✅ Контейнер test_history_db уже запущен")
            return True
        
        # Запускаем через docker-compose
        compose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docker-compose.yml"
        )
        
        if os.path.exists(compose_path):
            result = subprocess.run(
                ["docker-compose", "-f", compose_path, "up", "-d", "history-db"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print("✅ Контейнер запущен")
                print("⏳ Ожидание готовности PostgreSQL...")
                import time
                time.sleep(3)  # Даём время на инициализацию
                return True
            else:
                print(f"❌ Ошибка запуска: {result.stderr}")
                return False
        else:
            print(f"❌ Файл docker-compose.yml не найден: {compose_path}")
            return False
            
    except FileNotFoundError:
        print("❌ Docker не установлен или не доступен")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def create_database(config: dict, db_name: str = "test_history") -> bool:
    """Создать базу данных для истории если не существует"""
    # Подключаемся к postgres (системная БД) для создания новой БД
    system_url = build_connection_url(config, database="postgres")
    
    try:
        engine = create_engine(system_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            # Проверяем существует ли база
            result = conn.execute(text(
                f"SELECT 1 FROM pg_database WHERE datname = :db_name"
            ), {"db_name": db_name})
            exists = result.fetchone() is not None
            
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"✅ База данных '{db_name}' создана")
            else:
                print(f"ℹ️  База данных '{db_name}' уже существует")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания базы данных: {e}")
        return False


def create_tables(config: dict, db_name: str = "test_history") -> bool:
    """Создать таблицы в базе данных"""
    db_url = build_connection_url(config, database=db_name)
    
    try:
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        
        print("✅ Таблицы созданы успешно:")
        print("   • test_runs      - история тестов")
        print("   • test_results   - результаты по СУБД")
        print("   • time_series    - временные ряды метрик")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return False


def test_connection(config: dict) -> bool:
    """Проверить подключение к PostgreSQL"""
    url = build_connection_url(config, database="postgres")
    
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Не удалось подключиться к PostgreSQL: {e}")
        return False


def print_env_config(config: dict, db_name: str):
    """Вывести переменные окружения для .env файла"""
    host = config.get('host', 'localhost')
    port = config.get('port', 5432)
    user = config.get('user', 'postgres')
    password = config.get('password', '')
    
    url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    print("\n" + "=" * 50)
    print("Добавьте в .env файл:")
    print("=" * 50)
    print(f"HISTORY_DATABASE_URL={url}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Инициализация базы данных для истории тестов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Рекомендуется: использовать Docker (отдельный порт 5433)
  python scripts/init_history_db.py --docker
  
  # Использовать существующий PostgreSQL сервер (pagila)
  python scripts/init_history_db.py --use-pagila-server
  
  # Только создать таблицы (БД уже существует)
  python scripts/init_history_db.py --docker --skip-create
        """
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Использовать Docker контейнер (порт 5433, рекомендуется)"
    )
    parser.add_argument(
        "--use-pagila-server",
        action="store_true",
        help="Использовать тот же сервер PostgreSQL что и pagila (порт 5432)"
    )
    parser.add_argument(
        "--db-name", 
        default="test_history",
        help="Имя базы данных (по умолчанию: test_history)"
    )
    parser.add_argument(
        "--skip-create",
        action="store_true",
        help="Пропустить создание БД, только создать таблицы"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Инициализация базы данных истории тестов")
    print("=" * 50)
    
    # Определяем конфигурацию
    if args.docker:
        print("\n🐳 Режим: Docker контейнер (порт 5433)")
        
        # Запускаем контейнер если нужно
        if not start_docker_container():
            print("\n💡 Запустите вручную: docker-compose up -d history-db")
            sys.exit(1)
        
        config = DOCKER_CONFIG.copy()
        db_name = config['database']
        
    elif args.use_pagila_server:
        print("\n🐘 Режим: существующий PostgreSQL сервер")
        config = load_database_config()
        
        if not config:
            print("❌ Не найден файл config/database_config.yaml")
            sys.exit(1)
        
        db_name = args.db_name
    else:
        # По умолчанию используем Docker
        print("\n💡 Режим не указан, используем Docker (--docker)")
        print("   Для использования существующего сервера: --use-pagila-server")
        
        if not start_docker_container():
            print("\n⚠️  Docker недоступен, пробуем существующий сервер...")
            config = load_database_config()
            if not config:
                print("❌ Не найден config/database_config.yaml")
                sys.exit(1)
            db_name = args.db_name
        else:
            config = DOCKER_CONFIG.copy()
            db_name = config['database']
    
    host = config.get('host', 'localhost')
    port = config.get('port', 5432)
    user = config.get('user', 'postgres')
    
    print(f"\nПодключение: {user}@{host}:{port}")
    
    # Проверяем подключение
    print("\n🔍 Проверка подключения к PostgreSQL...")
    if not test_connection(config):
        print("\n💡 Подсказки:")
        if args.docker or port == 5433:
            print("   1. Запустите Docker контейнер: docker-compose up -d history-db")
            print("   2. Проверьте что Docker запущен")
        else:
            print("   1. Убедитесь, что PostgreSQL запущен")
            print("   2. Проверьте учетные данные в config/database_config.yaml")
        sys.exit(1)
    
    print("✅ Подключение успешно!")
    
    # Создаём базу данных (для Docker она уже создана)
    if not args.skip_create and not args.docker:
        print(f"\n📦 Создание базы данных '{db_name}'...")
        if not create_database(config, db_name):
            print("\n⚠️  Продолжаем с созданием таблиц...")
    
    # Создаём таблицы
    print(f"\n🏗️  Создание таблиц в '{db_name}'...")
    if not create_tables(config, db_name):
        print("\n❌ Инициализация завершилась с ошибками")
        sys.exit(1)
    
    # Выводим конфигурацию для .env
    print_env_config(config, db_name)
    
    print("\n✅ Инициализация завершена успешно!")
    print("\n💡 Следующие шаги:")
    print("   1. Скопируйте HISTORY_DATABASE_URL в .env файл")
    print("   2. Перезапустите backend: ./start_backend.sh")


if __name__ == "__main__":
    main()
