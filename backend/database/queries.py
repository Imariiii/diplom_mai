"""
Модуль с тестовыми запросами для Sakila/Pagila
"""
from typing import List, Dict

from backend.core.config import settings


class QueryManager:
    """Класс для управления тестовыми запросами"""
    
    def __init__(self):
        self.queries = self._load_queries()
    
    def _load_queries(self) -> List[Dict[str, str]]:
        """Загрузка запросов из централизованных настроек"""
        default_queries = settings.test.default_queries
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
