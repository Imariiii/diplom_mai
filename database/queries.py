"""
Модуль с тестовыми запросами для Sakila/Pagila
"""
from typing import List, Dict
import yaml
import os


class QueryManager:
    """Класс для управления тестовыми запросами"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Определяем путь относительно корня проекта (code/)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # Поднимаемся на уровень выше из database/
            config_path = os.path.join(project_root, "config", "database_config.yaml")
        self.config = self._load_config(config_path)
        self.queries = self._load_queries()
    
    def _load_config(self, config_path: str) -> dict:
        """Загрузка конфигурации"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            print(f"Предупреждение: Файл конфигурации не найден: {config_path}")
        return {}
    
    def _load_queries(self) -> List[Dict[str, str]]:
        """Загрузка запросов из конфигурации"""
        default_queries = self.config.get('test_settings', {}).get('default_queries', [])
        queries = []
        
        for i, query in enumerate(default_queries):
            queries.append({
                'id': f'query_{i+1}',
                'name': f'Запрос {i+1}',
                'sql': query,
                'description': f'Тестовый запрос #{i+1}'
            })
        
        return queries
    
    def get_all_queries(self) -> List[Dict[str, str]]:
        """Получить все запросы"""
        return self.queries
    
    def get_query(self, query_id: str) -> Dict[str, str]:
        """Получить конкретный запрос"""
        for query in self.queries:
            if query['id'] == query_id:
                return query
        raise ValueError(f"Запрос {query_id} не найден")
    
    def add_query(self, name: str, sql: str, description: str = "") -> Dict[str, str]:
        """Добавить новый запрос"""
        query_id = f'query_{len(self.queries) + 1}'
        new_query = {
            'id': query_id,
            'name': name,
            'sql': sql,
            'description': description
        }
        self.queries.append(new_query)
        return new_query

