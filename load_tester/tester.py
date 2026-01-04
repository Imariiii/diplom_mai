"""
Модуль для проведения нагрузочного тестирования
"""
import time
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import text
from database.connection import DatabaseConnection
from database.queries import QueryManager


class LoadTester:
    """Класс для проведения нагрузочного тестирования"""
    
    def __init__(self):
        self.db_connection = DatabaseConnection()
        self.query_manager = QueryManager()
        self.results: List[Dict] = []
    
    async def execute_query(self, db_type: str, query: str, query_id: str) -> Dict:
        """Выполнение одного запроса с измерением времени"""
        start_time = time.time()
        error = None
        rows_count = 0
        
        try:
            engine = self.db_connection.get_engine(db_type)
            with engine.connect() as conn:
                result = conn.execute(text(query))
                rows_count = len(result.fetchall()) if result.returns_rows else 0
                conn.commit()
        except Exception as e:
            error = str(e)
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # в миллисекундах
        
        return {
            'query_id': query_id,
            'db_type': db_type,
            'execution_time_ms': execution_time,
            'rows_count': rows_count,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
    
    async def run_single_test(self, db_type: str, query_id: str, iterations: int = 10) -> Dict:
        """Запуск одного теста с несколькими итерациями"""
        query = self.query_manager.get_query(query_id)
        results = []
        
        for i in range(iterations):
            result = await self.execute_query(db_type, query['sql'], query_id)
            results.append(result)
            await asyncio.sleep(0.1)  # Небольшая задержка между запросами
        
        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        
        if execution_times:
            stats = {
                'query_id': query_id,
                'db_type': db_type,
                'iterations': iterations,
                'successful': len(execution_times),
                'failed': len(results) - len(execution_times),
                'avg_time_ms': sum(execution_times) / len(execution_times),
                'min_time_ms': min(execution_times),
                'max_time_ms': max(execution_times),
                'total_time_ms': sum(execution_times),
                'timestamp': datetime.now().isoformat()
            }
        else:
            stats = {
                'query_id': query_id,
                'db_type': db_type,
                'iterations': iterations,
                'successful': 0,
                'failed': len(results),
                'error': 'Все запросы завершились с ошибкой',
                'timestamp': datetime.now().isoformat()
            }
        
        return stats
    
    async def run_comparison_test(
        self, 
        query_id: str, 
        db_types: List[str] = None,
        iterations: int = 10
    ) -> Dict:
        """Запуск сравнительного теста для нескольких БД"""
        if db_types is None:
            db_types = ['mysql', 'postgresql']
        
        results = {}
        
        for db_type in db_types:
            print(f"Тестирование {db_type}...")
            stats = await self.run_single_test(db_type, query_id, iterations)
            results[db_type] = stats
        
        return {
            'query_id': query_id,
            'comparison': results,
            'timestamp': datetime.now().isoformat()
        }
    
    async def run_full_test_suite(
        self,
        db_types: List[str] = None,
        iterations: int = 10
    ) -> List[Dict]:
        """Запуск полного набора тестов"""
        if db_types is None:
            db_types = ['mysql', 'postgresql']
        
        queries = self.query_manager.get_all_queries()
        all_results = []
        
        for query in queries:
            print(f"Тестирование запроса: {query['name']}")
            comparison = await self.run_comparison_test(
                query['id'],
                db_types,
                iterations
            )
            all_results.append(comparison)
        
        return all_results
    
    def close(self):
        """Закрытие подключений"""
        self.db_connection.close_all()

