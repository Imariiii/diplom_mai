"""
Модуль для подключения к различным СУБД
"""
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.pool import QueuePool
from typing import Dict
import yaml
import os


class DatabaseConnection:
    """Класс для управления подключениями к базам данных"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Определяем путь относительно корня проекта (code/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Поднимаемся на уровень выше из database/
            config_path = os.path.join(project_root, "config", "database_config.yaml")
        self.config = self._load_config(config_path)
        self.engines: Dict[str, Engine] = {}
    
    def _load_config(self, config_path: str) -> dict:
        """Загрузка конфигурации из YAML файла"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            print(f"Предупреждение: Файл конфигурации не найден: {config_path}")
        return {}
    
    def get_connection_string(self, db_type: str) -> str:
        """Формирование строки подключения"""
        db_config = self.config.get('databases', {}).get(db_type, {})
        
        if db_type == 'mysql':
            return (
                f"mysql+pymysql://{db_config.get('user')}:{db_config.get('password')}"
                f"@{db_config.get('host')}:{db_config.get('port')}"
                f"/{db_config.get('database')}"
            )
        elif db_type == 'postgresql':
            return (
                f"postgresql+psycopg2://{db_config.get('user')}:{db_config.get('password')}"
                f"@{db_config.get('host')}:{db_config.get('port')}"
                f"/{db_config.get('database')}"
            )
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {db_type}")
    
    def get_engine(self, db_type: str) -> Engine:
        """Получение или создание engine для подключения"""
        if db_type not in self.engines:
            connection_string = self.get_connection_string(db_type)
            self.engines[db_type] = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                echo=False
            )
        return self.engines[db_type]
    
    def test_connection(self, db_type: str) -> bool:
        """Проверка подключения к БД"""
        try:
            engine = self.get_engine(db_type)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Ошибка подключения к {db_type}: {e}")
            return False
    
    def close_all(self):
        """Закрытие всех подключений"""
        for engine in self.engines.values():
            engine.dispose()
        self.engines.clear()
    
    def recreate_engine(self, db_type: str) -> Engine:
        """
        Пересоздать engine для указанной СУБД
        Закрывает старые соединения и создаёт новый engine
        """
        if db_type in self.engines:
            self.engines[db_type].dispose()
            del self.engines[db_type]
        return self.get_engine(db_type)
    
    async def terminate_other_connections(self, engine: Engine, db_type: str) -> int:
        """
        Завершить другие активные соединения с БД
        
        Returns:
            Количество завершённых соединений
        """
        terminated = 0
        
        with engine.connect() as conn:
            if db_type == 'postgresql':
                # PostgreSQL: используем pg_terminate_backend
                sql = """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    AND pid <> pg_backend_pid()
                    AND state != 'idle'
                """
                result = conn.execute(text(sql))
                terminated = sum(1 for row in result if row[0])
                conn.commit()
                
            elif db_type == 'mysql':
                # MySQL: используем KILL
                # Получаем список процессов
                result = conn.execute(text("SHOW PROCESSLIST"))
                rows = result.fetchall()
                
                for row in rows:
                    process_id = row[0]
                    process_db = row[3] if len(row) > 3 else None
                    process_command = row[4] if len(row) > 4 else None
                    
                    # Не убиваем собственное соединение и системные процессы
                    if (process_command != 'Sleep' and 
                        process_db == self.config.get('databases', {}).get(db_type, {}).get('database')):
                        try:
                            conn.execute(text(f"KILL {process_id}"))
                            terminated += 1
                        except:
                            pass
                
                conn.commit()
        
        return terminated

