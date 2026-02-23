"""
Модуль для проведения нагрузочного тестирования
"""
import time
import asyncio
import statistics
import psutil
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from sqlalchemy import text
from backend.database.connection import DatabaseConnection
from backend.database.queries import QueryManager


class LoadTester:
    """Класс для проведения нагрузочного тестирования"""
    
    def __init__(self):
        self.db_connection = DatabaseConnection()
        self.query_manager = QueryManager()
        self.results: List[Dict] = []
        
        # Callback для real-time обновлений
        self._metrics_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        self._is_streaming: bool = False
        self._streaming_interval: float = 1.0  # Интервал отправки метрик в секундах
    
    def set_streaming_callback(self, callback: Any):
        """Установить callback для потоковой отправки метрик"""
        self._metrics_callback = callback
        self._is_streaming = callback is not None
    
    def set_status_callback(self, callback: Callable):
        """Установить callback для обновления статуса"""
        self._status_callback = callback
    
    async def _emit_metrics(
        self, 
        db_type: str, 
        response_time: float, 
        tps: float,
        successful: int,
        failed: int
    ):
        """Отправить метрики через callback"""
        if self._metrics_callback and self._is_streaming:
            try:
                # Получаем системные метрики
                system_metrics = await self.get_system_metrics(db_type)
                
                await self._metrics_callback.on_metrics(
                    db_type=db_type,
                    response_time=response_time,
                    tps=tps,
                    successful=successful,
                    failed=failed,
                    cpu_usage=system_metrics.get('cpu_usage', 0),
                    memory_usage=system_metrics.get('memory_usage_percent', 0),
                    memory_usage_mb=system_metrics.get('memory_usage_mb', 0),
                    disk_iops=system_metrics.get('disk_iops', 0),
                    network_in=system_metrics.get('network_in_mbps', 0),
                    network_out=system_metrics.get('network_out_mbps', 0)
                )
            except Exception as e:
                print(f"Ошибка отправки метрик: {e}")
    
    async def _emit_status(self, status: str, message: str = None):
        """Отправить статус через callback"""
        if self._metrics_callback:
            try:
                await self._metrics_callback.on_status_change(status, message)
            except Exception as e:
                print(f"Ошибка отправки статуса: {e}")
    
    def calculate_percentile(self, data: List[float], percentile: float) -> float:
        """Вычисление перцентиля"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]
    
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
    
    async def run_single_test(
        self, 
        db_type: str, 
        query_id: str, 
        iterations: int = 10,
        virtual_users: int = 1,
        scenario: str = "mixed_light"
    ) -> Dict:
        """Запуск одного теста с несколькими итерациями"""
        query = self.query_manager.get_query(query_id)
        results = []
        start_time = time.time()
        last_emit_time = start_time
        
        # Буферы для потоковых метрик
        recent_times = []
        recent_successful = 0
        recent_failed = 0
        
        # Запуск итераций (симуляция виртуальных пользователей)
        for i in range(iterations):
            result = await self.execute_query(db_type, query['sql'], query_id)
            results.append(result)
            
            # Накапливаем метрики для потоковой отправки
            if result['error'] is None:
                recent_times.append(result['execution_time_ms'])
                recent_successful += 1
            else:
                recent_failed += 1
            
            # Отправляем метрики каждые N миллисекунд
            current_time = time.time()
            if self._is_streaming and (current_time - last_emit_time) >= self._streaming_interval:
                if recent_times:
                    avg_response_time = statistics.mean(recent_times) if recent_times else 0
                    elapsed = current_time - start_time
                    tps = (recent_successful + recent_failed) / (current_time - last_emit_time) if (current_time - last_emit_time) > 0 else 0
                    
                    await self._emit_metrics(
                        db_type=db_type,
                        response_time=avg_response_time,
                        tps=tps,
                        successful=recent_successful,
                        failed=recent_failed
                    )
                
                # Сбрасываем буферы
                recent_times = []
                recent_successful = 0
                recent_failed = 0
                last_emit_time = current_time
            
            await asyncio.sleep(0.01)  # Небольшая задержка между запросами
        
        end_time = time.time()
        total_test_time = end_time - start_time
        
        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        
        if execution_times:
            successful_count = len(execution_times)
            failed_count = len(results) - len(execution_times)
            
            stats = {
                'query_id': query_id,
                'db_type': db_type,
                'iterations': iterations,
                'virtual_users': virtual_users,
                'scenario': scenario,
                'successful': successful_count,
                'failed': failed_count,
                
                # Время отклика
                'avg_time_ms': statistics.mean(execution_times),
                'min_time_ms': min(execution_times),
                'max_time_ms': max(execution_times),
                'p50_time_ms': self.calculate_percentile(execution_times, 50),
                'p95_time_ms': self.calculate_percentile(execution_times, 95),
                'p99_time_ms': self.calculate_percentile(execution_times, 99),
                'total_time_ms': sum(execution_times),
                'std_dev_ms': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                
                # TPS (Транзакций в секунду)
                'tps': successful_count / total_test_time if total_test_time > 0 else 0,
                'throughput': successful_count / total_test_time if total_test_time > 0 else 0,
                
                # Активные соединения
                'active_connections': virtual_users,
                
                # Количество ошибок
                'error_count': failed_count,
                'error_rate': (failed_count / iterations) * 100 if iterations > 0 else 0,
                
                'timestamp': datetime.now().isoformat()
            }
        else:
            stats = {
                'query_id': query_id,
                'db_type': db_type,
                'iterations': iterations,
                'virtual_users': virtual_users,
                'scenario': scenario,
                'successful': 0,
                'failed': len(results),
                'error': 'Все запросы завершились с ошибкой',
                'tps': 0,
                'throughput': 0,
                'active_connections': virtual_users,
                'error_count': len(results),
                'error_rate': 100,
                'timestamp': datetime.now().isoformat()
            }
        
        return stats
    
    async def run_comparison_test(
        self, 
        query_id: str, 
        db_types: List[str] = None,
        iterations: int = 10,
        virtual_users: int = 1,
        scenario: str = "mixed_light"
    ) -> Dict:
        """Запуск сравнительного теста для нескольких БД"""
        if db_types is None:
            db_types = ['mysql', 'postgresql']
        
        results = {}
        
        for db_type in db_types:
            print(f"Тестирование {db_type}...")
            stats = await self.run_single_test(
                db_type, 
                query_id, 
                iterations,
                virtual_users=virtual_users,
                scenario=scenario
            )
            results[db_type] = stats
        
        return {
            'query_id': query_id,
            'comparison': results,
            'timestamp': datetime.now().isoformat()
        }
    
    async def run_full_test_suite(
        self,
        db_types: List[str] = None,
        iterations: int = 10,
        duration: int = 60,
        virtual_users: int = 10,
        scenario: str = "mixed_light",
        warmup_time: int = 5
    ) -> List[Dict]:
        """Запуск полного набора тестов"""
        if db_types is None:
            db_types = ['mysql', 'postgresql']
        
        queries = self.query_manager.get_all_queries()
        all_results = []
        total_queries = len(queries)
        
        # Устанавливаем количество запросов для расчёта прогресса
        if self._metrics_callback:
            self._metrics_callback.set_total_queries(total_queries)
            await self._metrics_callback.on_test_start()
        
        # Прогрев (если указан)
        if warmup_time > 0:
            print(f"Прогрев системы ({warmup_time} сек)...")
            await self._emit_status("running", f"Прогрев системы ({warmup_time} сек)...")
            
            warmup_query = queries[0] if queries else None
            if warmup_query:
                for db_type in db_types:
                    for _ in range(min(5, iterations)):
                        await self.execute_query(db_type, warmup_query['sql'], warmup_query['id'])
                        await asyncio.sleep(0.1)
            await asyncio.sleep(warmup_time)
        
        for idx, query in enumerate(queries):
            print(f"Тестирование запроса: {query['name']} ({idx + 1}/{total_queries})")
            
            # Обновляем прогресс
            if self._metrics_callback:
                self._metrics_callback.set_current_query(idx + 1)
            
            await self._emit_status("running", f"Тестирование: {query['name']} ({idx + 1}/{total_queries})")
            
            comparison = await self.run_comparison_test(
                query['id'],
                db_types,
                iterations,
                virtual_users=virtual_users,
                scenario=scenario
            )
            all_results.append(comparison)
        
        # Уведомляем о завершении
        if self._metrics_callback:
            total_transactions = sum(
                stats.get('successful', 0) + stats.get('failed', 0)
                for result in all_results
                for stats in result.get('comparison', {}).values()
            )
            summary = {
                'total_transactions': total_transactions,
                'overall_tps': total_transactions / total_queries if total_queries > 0 else 0,
            }
            await self._metrics_callback.on_test_complete(summary)
        
        return all_results
    
    async def get_system_metrics(self, db_type: str) -> Dict:
        """Получить системные метрики"""
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage_mb': memory.used / (1024 * 1024),
                'memory_usage_percent': memory.percent,
                'disk_iops': disk_io.read_count + disk_io.write_count if disk_io else 0,
                'disk_read_mbps': disk_io.read_bytes / (1024 * 1024) if disk_io else 0,
                'disk_write_mbps': disk_io.write_bytes / (1024 * 1024) if disk_io else 0,
                'network_in_mbps': network_io.bytes_recv / (1024 * 1024) if network_io else 0,
                'network_out_mbps': network_io.bytes_sent / (1024 * 1024) if network_io else 0,
            }
        except Exception as e:
            print(f"Ошибка получения системных метрик: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage_mb': 0,
                'memory_usage_percent': 0,
                'disk_iops': 0,
                'disk_read_mbps': 0,
                'disk_write_mbps': 0,
                'network_in_mbps': 0,
                'network_out_mbps': 0,
            }
    
    async def get_dbms_metrics(self, db_type: str) -> Dict:
        """Получить внутренние метрики СУБД"""
        metrics = {
            'cache_hit_ratio': 0,
            'buffer_pool_hit_ratio': 0,
            'lock_waits': 0,
            'deadlocks': 0,
            'active_connections': 0,
            'table_sizes_mb': {},
            'index_sizes_mb': {},
            'total_db_size_mb': 0,
        }
        
        try:
            engine = self.db_connection.get_engine(db_type)
            
            if db_type == 'postgresql':
                with engine.connect() as conn:
                    # Cache hit ratio
                    result = conn.execute(text("""
                        SELECT 
                            CASE WHEN blks_hit + blks_read = 0 THEN 0
                            ELSE round(100.0 * blks_hit / (blks_hit + blks_read), 2)
                            END as cache_hit_ratio
                        FROM pg_stat_database 
                        WHERE datname = current_database()
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['cache_hit_ratio'] = float(row[0] or 0)
                        metrics['buffer_pool_hit_ratio'] = float(row[0] or 0)
                    
                    # Active connections
                    result = conn.execute(text("""
                        SELECT count(*) FROM pg_stat_activity 
                        WHERE datname = current_database()
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['active_connections'] = int(row[0] or 0)
                    
                    # Lock waits
                    result = conn.execute(text("""
                        SELECT count(*) FROM pg_locks WHERE NOT granted
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['lock_waits'] = int(row[0] or 0)
                    
                    # Table sizes
                    result = conn.execute(text("""
                        SELECT relname, pg_total_relation_size(relid) / (1024*1024) as size_mb
                        FROM pg_stat_user_tables
                        ORDER BY pg_total_relation_size(relid) DESC
                        LIMIT 10
                    """))
                    for row in result:
                        metrics['table_sizes_mb'][row[0]] = float(row[1] or 0)
                    
                    # Total DB size
                    result = conn.execute(text("""
                        SELECT pg_database_size(current_database()) / (1024*1024) as size_mb
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['total_db_size_mb'] = float(row[0] or 0)
                    
            elif db_type == 'mysql':
                with engine.connect() as conn:
                    # Buffer pool hit ratio
                    result = conn.execute(text("""
                        SELECT 
                            (1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)) * 100 
                            as hit_ratio
                        FROM (
                            SELECT 
                                (SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                                 WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') as Innodb_buffer_pool_reads,
                                (SELECT VARIABLE_VALUE FROM performance_schema.global_status 
                                 WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests') as Innodb_buffer_pool_read_requests
                        ) as stats
                    """))
                    row = result.fetchone()
                    if row and row[0]:
                        metrics['buffer_pool_hit_ratio'] = float(row[0])
                        metrics['cache_hit_ratio'] = float(row[0])
                    
                    # Active connections
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.PROCESSLIST
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['active_connections'] = int(row[0] or 0)
                    
                    # Lock waits
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM performance_schema.data_lock_waits
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['lock_waits'] = int(row[0] or 0)
                    
                    # Table sizes
                    result = conn.execute(text("""
                        SELECT TABLE_NAME, 
                               ROUND((DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                        ORDER BY (DATA_LENGTH + INDEX_LENGTH) DESC
                        LIMIT 10
                    """))
                    for row in result:
                        metrics['table_sizes_mb'][row[0]] = float(row[1] or 0)
                    
                    # Total DB size
                    result = conn.execute(text("""
                        SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['total_db_size_mb'] = float(row[0] or 0)
                        
        except Exception as e:
            print(f"Ошибка получения метрик СУБД {db_type}: {e}")
        
        return metrics
    
    def close(self):
        """Закрытие подключений"""
        self.db_connection.close_all()
