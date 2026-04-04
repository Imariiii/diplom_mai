"""
Модуль для проведения нагрузочного тестирования
"""
import time
import asyncio
import statistics
import psutil
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone
from sqlalchemy import text
from backend.database.connection import DatabaseConnection
from backend.database.queries import QueryManager
from backend.database.state_manager import DatabaseStateManager


class LoadTester:
    """Класс для проведения нагрузочного тестирования"""
    
    def __init__(self, connection_repo=None):
        self.db_connection = DatabaseConnection()
        if connection_repo:
            self.db_connection.set_connection_repository(connection_repo)
        self.query_manager = QueryManager()
        self.state_manager = DatabaseStateManager()
        self.results: List[Dict] = []
        
        # Callback для real-time обновлений
        self._metrics_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        self._backup_callback: Optional[Callable] = None  # Callback для backup/restore статусов
        self._is_streaming: bool = False
        self._streaming_interval: float = 1.0  # Интервал отправки метрик в секундах
    
    def set_streaming_callback(self, callback: Any):
        """Установить callback для потоковой отправки метрик"""
        self._metrics_callback = callback
        self._is_streaming = callback is not None
    
    def set_backup_callback(self, callback: Callable):
        """Установить callback для статуса backup/restore"""
        self._backup_callback = callback
    
    async def _emit_backup_status(self, status: str, data: Dict = None):
        """Отправить статус backup/restore через callback"""
        if self._backup_callback:
            try:
                await self._backup_callback(status, data or {})
            except Exception as e:
                print(f"Ошибка отправки статуса backup: {e}")
    
    def set_status_callback(self, callback: Callable):
        """Установить callback для обновления статуса"""
        self._status_callback = callback
    
    async def _emit_metrics(
        self,
        db_key: str,
        response_time: float, 
        tps: float,
        successful: int,
        failed: int
    ):
        """Отправить метрики через callback"""
        if self._metrics_callback and self._is_streaming:
            try:
                db_type = self.db_connection.get_dbms_type(db_key)
                db_name = self.db_connection.get_connection_name(db_key)
                
                # Получаем системные метрики
                system_metrics = await self.get_system_metrics(db_key)
                
                # Получаем внутренние метрики СУБД
                dbms_metrics = await self.get_dbms_metrics(db_key)
                
                await self._metrics_callback.on_metrics(
                    db_key=db_key,
                    db_type=db_type,
                    db_name=db_name,
                    response_time=response_time,
                    tps=tps,
                    successful=successful,
                    failed=failed,
                    cpu_usage=system_metrics.get('cpu_usage', 0),
                    memory_usage=system_metrics.get('memory_usage_percent', 0),
                    memory_usage_mb=system_metrics.get('memory_usage_mb', 0),
                    disk_iops=system_metrics.get('disk_iops', 0),
                    network_in=system_metrics.get('network_in_mbps', 0),
                    network_out=system_metrics.get('network_out_mbps', 0),
                    cache_hit_ratio=dbms_metrics.get('cache_hit_ratio', 0),
                    buffer_pool_hit_ratio=dbms_metrics.get('buffer_pool_hit_ratio', 0),
                    lock_waits=dbms_metrics.get('lock_waits', 0),
                    deadlocks=dbms_metrics.get('deadlocks', 0)
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
    
    async def execute_query(self, db_key: str, query: str, query_id: str) -> Dict:
        """Выполнение одного запроса с измерением времени"""
        start_time = time.perf_counter()
        error = None
        rows_count = 0
        db_type = self.db_connection.get_dbms_type(db_key)
        
        try:
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                result = await conn.execute(text(query))
                rows_count = len(result.fetchall()) if result.returns_rows else 0
                await conn.commit()
        except Exception as e:
            error = str(e)
        
        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000  # в миллисекундах
        
        return {
            'query_id': query_id,
            'db_key': db_key,
            'db_type': db_type,
            'execution_time_ms': execution_time,
            'rows_count': rows_count,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def run_single_test(
        self, 
        db_key: str, 
        query_id: str, 
        iterations: int = 10,
        virtual_users: int = 1,
        scenario: str = "mixed_light",
        auto_restore: bool = True
    ) -> Dict:
        """Запуск одного теста с несколькими итерациями и автовосстановлением БД"""
        query = self.query_manager.get_query(query_id)
        queries = [query['sql']]
        
        # Подготовка БД (backup если нужно)
        prepare_info = await self.prepare_database_for_test(
            db_key, queries, auto_restore
        )
        
        results = []
        start_time = time.perf_counter()
        last_emit_time = start_time
        
        # Буферы для потоковых метрик
        recent_times = []
        recent_successful = 0
        recent_failed = 0
        
        try:
            # Запуск итераций (симуляция виртуальных пользователей)
            for i in range(iterations):
                result = await self.execute_query(db_key, query['sql'], query_id)
                results.append(result)
                
                # Накапливаем метрики для потоковой отправки
                if result['error'] is None:
                    recent_times.append(result['execution_time_ms'])
                    recent_successful += 1
                else:
                    recent_failed += 1
                
                # Отправляем метрики каждые N миллисекунд
                current_time = time.perf_counter()
                if self._is_streaming and (current_time - last_emit_time) >= self._streaming_interval:
                    if recent_times:
                        avg_response_time = statistics.mean(recent_times) if recent_times else 0
                        elapsed = current_time - start_time
                        tps = (recent_successful + recent_failed) / (current_time - last_emit_time) if (current_time - last_emit_time) > 0 else 0
                        
                        await self._emit_metrics(
                            db_key=db_key,
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
            
            end_time = time.perf_counter()
            total_test_time = end_time - start_time
            
        finally:
            # Восстановление БД (даже при ошибке)
            restore_info = await self.restore_database_after_test(
                db_key, prepare_info, auto_restore
            )
        
        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        
        db_type = self.db_connection.get_dbms_type(db_key)

        if execution_times:
            successful_count = len(execution_times)
            failed_count = len(results) - len(execution_times)
            
            stats = {
                'query_id': query_id,
                'db_key': db_key,
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
                
                # Информация о restore
                'restore_info': {
                    'needed': prepare_info.get('needs_restore', False),
                    'restored': restore_info.get('restored', False),
                    'affected_tables': prepare_info.get('affected_tables', []),
                    'duration_ms': restore_info.get('duration_ms'),
                    'verified': restore_info.get('verified'),
                    'errors': restore_info.get('errors')
                },
                
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            stats = {
                'query_id': query_id,
                'db_key': db_key,
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
                'restore_info': {
                    'needed': prepare_info.get('needs_restore', False),
                    'restored': restore_info.get('restored', False),
                    'affected_tables': prepare_info.get('affected_tables', []),
                    'duration_ms': restore_info.get('duration_ms'),
                    'verified': restore_info.get('verified'),
                    'errors': restore_info.get('errors')
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        return stats
    
    async def run_comparison_test(
        self, 
        query_id: str, 
        db_types: List[str] = None,
        iterations: int = 10,
        virtual_users: int = 1,
        scenario: str = "mixed_light",
        auto_restore: bool = True
    ) -> Dict:
        """Запуск сравнительного теста для нескольких БД с автовосстановлением"""
        if db_types is None:
            db_types = ['mysql', 'postgresql']
        
        results = {}
        prepare_infos = {}
        
        # Получаем запрос для анализа
        query = self.query_manager.get_query(query_id)
        queries = [query['sql']]
        
        # Подготовка для всех БД
        for db_key in db_types:
            print(f"Подготовка {db_key}...")
            prepare_info = await self.prepare_database_for_test(
                db_key, queries, auto_restore
            )
            prepare_infos[db_key] = prepare_info
        
        # Запуск тестов
        try:
            for db_key in db_types:
                print(f"Тестирование {db_key}...")
                stats = await self.run_single_test(
                    db_key, 
                    query_id, 
                    iterations,
                    virtual_users=virtual_users,
                    scenario=scenario,
                    auto_restore=False  # Restore сделаем вручную после всех тестов
                )
                results[db_key] = stats
        finally:
            # Восстановление всех БД
            for db_key in db_types:
                if prepare_infos[db_key].get('needs_restore'):
                    await self.restore_database_after_test(
                        db_key, prepare_infos[db_key], auto_restore
                    )
        
        return {
            'query_id': query_id,
            'comparison': results,
            'restore_info': {
                db_key: {
                    'needed': info.get('needs_restore', False),
                    'affected_tables': info.get('affected_tables', [])
                }
                for db_key, info in prepare_infos.items()
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
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
    
    async def get_system_metrics(self, db_key: str) -> Dict:
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
    
    async def get_dbms_metrics(self, db_key: str) -> Dict:
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
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            
            if db_type == 'postgresql':
                async with engine.connect() as conn:
                    # Cache hit ratio
                    result = await conn.execute(text("""
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
                    result = await conn.execute(text("""
                        SELECT count(*) FROM pg_stat_activity 
                        WHERE datname = current_database()
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['active_connections'] = int(row[0] or 0)
                    
                    # Lock waits
                    result = await conn.execute(text("""
                        SELECT count(*) FROM pg_locks WHERE NOT granted
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['lock_waits'] = int(row[0] or 0)
                    
                    # Table sizes
                    result = await conn.execute(text("""
                        SELECT relname, pg_total_relation_size(relid) / (1024*1024) as size_mb
                        FROM pg_stat_user_tables
                        ORDER BY pg_total_relation_size(relid) DESC
                        LIMIT 10
                    """))
                    for row in result:
                        metrics['table_sizes_mb'][row[0]] = float(row[1] or 0)
                    
                    # Total DB size
                    result = await conn.execute(text("""
                        SELECT pg_database_size(current_database()) / (1024*1024) as size_mb
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['total_db_size_mb'] = float(row[0] or 0)
                    
            elif db_type == 'mysql':
                async with engine.connect() as conn:
                    # Buffer pool hit ratio
                    result = await conn.execute(text("""
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
                    result = await conn.execute(text("""
                        SELECT COUNT(*) FROM information_schema.PROCESSLIST
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['active_connections'] = int(row[0] or 0)
                    
                    # Lock waits
                    result = await conn.execute(text("""
                        SELECT COUNT(*) FROM performance_schema.data_lock_waits
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['lock_waits'] = int(row[0] or 0)
                    
                    # Table sizes
                    result = await conn.execute(text("""
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
                    result = await conn.execute(text("""
                        SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE()
                    """))
                    row = result.fetchone()
                    if row:
                        metrics['total_db_size_mb'] = float(row[0] or 0)
                        
        except Exception as e:
            print(f"Ошибка получения метрик СУБД {db_key}: {e}")
        
        return metrics
    
    async def execute_scenario_query(
        self,
        db_key: str,
        sql_template: str,
        params_config: List[Dict],
        scenario_name: str
    ) -> Dict:
        """Выполнение запроса сценария с подстановкой параметров"""
        start_time = time.perf_counter()
        error = None
        rows_count = 0
        db_type = self.db_connection.get_dbms_type(db_key)

        # Подстановка параметров
        param_values = {}
        for param_config in params_config:
            param_name = param_config['param_name']
            param_type = param_config['param_type']
            param_values[param_name] = await self._generate_param_value(
                db_key, param_type, param_config
            )

        # Формируем финальный SQL
        try:
            final_sql = sql_template.format(**param_values)
        except KeyError as e:
            error = f"Missing parameter: {e}"
            final_sql = sql_template

        try:
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                result = await conn.execute(text(final_sql))
                rows_count = len(result.fetchall()) if result.returns_rows else 0
                await conn.commit()
        except Exception as e:
            error = str(e)

        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000

        return {
            'scenario': scenario_name,
            'db_key': db_key,
            'db_type': db_type,
            'sql': final_sql[:200] + '...' if len(final_sql) > 200 else final_sql,
            'execution_time_ms': execution_time,
            'rows_count': rows_count,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    async def _generate_param_value(
        self,
        db_key: str,
        param_type: str,
        param_config: Dict
    ) -> Any:
        """Генерация значения параметра"""
        import random
        import uuid

        if param_type == 'random_int':
            min_val = param_config.get('min_value', 1)
            max_val = param_config.get('max_value', 1000)
            return random.randint(min_val, max_val)

        elif param_type == 'random_from_table':
            table = param_config.get('table_ref', '')
            column = param_config.get('column_ref', '')
            return await self._get_random_value_from_table(db_key, table, column)

        elif param_type == 'sequential_int':
            # Для sequential используем текущее время как seed
            return int(datetime.now().timestamp()) % 100000

        elif param_type == 'uuid':
            return str(uuid.uuid4())

        elif param_type == 'fixed':
            return param_config.get('fixed_value', '')

        elif param_type == 'random_string':
            length = param_config.get('string_length', 10)
            chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            return ''.join(random.choice(chars) for _ in range(length))

        elif param_type == 'random_date':
            from datetime import timedelta
            days = random.randint(0, 3650)  # ~10 years
            base_date = datetime(2000, 1, 1)
            return (base_date + timedelta(days=days)).strftime('%Y-%m-%d')

        else:
            return 1  # Default fallback

    async def _get_random_value_from_table(
        self,
        db_key: str,
        table: str,
        column: str
    ) -> Any:
        """Получение случайного значения из таблицы"""
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                result = await conn.execute(text(f"""
                    SELECT {column} FROM {table}
                    ORDER BY RANDOM() LIMIT 1
                """))
                row = result.fetchone()
                return row[0] if row else 1
        except Exception as e:
            print(f"Error getting random value: {e}")
            return 1

    async def run_scenario_test(
        self,
        db_key: str,
        scenario: Dict,
        iterations: int = 10,
        virtual_users: int = 1,
        auto_restore: bool = True
    ) -> Dict:
        """Запуск теста на основе сценария с автовосстановлением БД"""
        import random

        queries = scenario.get('queries', [])
        if not queries:
            return {
                'scenario': scenario.get('name', 'unknown'),
                'db_key': db_key,
                'db_type': self.db_connection.get_dbms_type(db_key),
                'error': 'No queries in scenario',
                'successful': 0,
                'failed': 0
            }

        # Получаем SQL запросы для анализа
        sql_queries = [q['sql_template'] for q in queries]
        
        # Подготовка БД
        prepare_info = await self.prepare_database_for_test(
            db_key, sql_queries, auto_restore
        )

        results = []
        start_time = time.perf_counter()

        # Создаем взвешенный список запросов
        weighted_queries = []
        for query in queries:
            weight = query.get('weight', 1)
            for _ in range(weight):
                weighted_queries.append(query)

        last_emit_time = start_time
        recent_times = []
        recent_successful = 0
        recent_failed = 0

        try:
            for i in range(iterations):
                # Выбираем случайный запрос из взвешенного списка
                query = random.choice(weighted_queries)

                result = await self.execute_scenario_query(
                    db_key,
                    query['sql_template'],
                    query.get('params', []),
                    scenario.get('name', 'unknown')
                )
                results.append(result)

                if result['error'] is None:
                    recent_times.append(result['execution_time_ms'])
                    recent_successful += 1
                else:
                    recent_failed += 1

                # Потоковая отправка метрик
                current_time = time.perf_counter()
                if self._is_streaming and (current_time - last_emit_time) >= self._streaming_interval:
                    if recent_times:
                        avg_response_time = statistics.mean(recent_times)
                        tps = (recent_successful + recent_failed) / (current_time - last_emit_time)

                        await self._emit_metrics(
                            db_key=db_key,
                            response_time=avg_response_time,
                            tps=tps,
                            successful=recent_successful,
                            failed=recent_failed
                        )

                    recent_times = []
                    recent_successful = 0
                    recent_failed = 0
                    last_emit_time = current_time

                await asyncio.sleep(0.01)

            end_time = time.perf_counter()
            total_test_time = end_time - start_time
            
        finally:
            # Восстановление БД
            restore_info = await self.restore_database_after_test(
                db_key, prepare_info, auto_restore
            )

        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        successful_count = len(execution_times)
        failed_count = len(results) - len(execution_times)

        db_type = self.db_connection.get_dbms_type(db_key)

        stats = {
            'scenario': scenario.get('name', 'unknown'),
            'scenario_type': scenario.get('scenario_type', 'unknown'),
            'db_key': db_key,
            'db_type': db_type,
            'iterations': iterations,
            'virtual_users': virtual_users,
            'successful': successful_count,
            'failed': failed_count,
            'avg_time_ms': statistics.mean(execution_times) if execution_times else 0,
            'min_time_ms': min(execution_times) if execution_times else 0,
            'max_time_ms': max(execution_times) if execution_times else 0,
            'p50_time_ms': self.calculate_percentile(execution_times, 50) if execution_times else 0,
            'p95_time_ms': self.calculate_percentile(execution_times, 95) if execution_times else 0,
            'p99_time_ms': self.calculate_percentile(execution_times, 99) if execution_times else 0,
            'tps': successful_count / total_test_time if total_test_time > 0 else 0,
            'throughput': successful_count / total_test_time if total_test_time > 0 else 0,
            'error_rate': (failed_count / iterations) * 100 if iterations > 0 else 0,
            'restore_info': {
                'needed': prepare_info.get('needs_restore', False),
                'restored': restore_info.get('restored', False),
                'affected_tables': prepare_info.get('affected_tables', []),
                'duration_ms': restore_info.get('duration_ms'),
                'verified': restore_info.get('verified'),
                'errors': restore_info.get('errors')
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        return stats

    async def run_full_scenario_test_suite(
        self,
        scenario_id: str,
        db_types: List[str] = None,
        iterations: int = 100,
        virtual_users: int = 10,
        warmup_time: int = 5,
        scenario_repository = None
    ) -> List[Dict]:
        """Запуск полного теста на основе сценария из БД"""
        from backend.database.repository import ScenarioRepository

        if db_types is None:
            db_types = ['mysql', 'postgresql']

        # Загружаем сценарий - используем переданный репозиторий или создаем новый
        if scenario_repository is not None:
            scenario_repo = scenario_repository
        else:
            # Fallback: создаем репозиторий с дефолтным URL
            import os
            db_url = os.getenv('HISTORY_DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5433/test_history')
            scenario_repo = ScenarioRepository(db_url)
        
        scenario = await scenario_repo.get_scenario_for_execution(scenario_id)

        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        all_results = []

        # Устанавливаем количество БД для прогресса
        if self._metrics_callback:
            self._metrics_callback.set_total_queries(len(db_types))
            await self._metrics_callback.on_test_start()

        # Прогрев
        if warmup_time > 0:
            print(f"Прогрев системы ({warmup_time} сек)...")
            await self._emit_status("running", f"Прогрев системы ({warmup_time} сек)...")

            queries = scenario.get('queries', [])
            if queries:
                warmup_query = queries[0]
                for db_key in db_types:
                    for _ in range(min(5, iterations // 10)):
                        await self.execute_scenario_query(
                            db_key,
                            warmup_query['sql_template'],
                            warmup_query.get('params', []),
                            scenario['name']
                        )
                        await asyncio.sleep(0.1)
            await asyncio.sleep(warmup_time)

        # Запуск тестов для каждой БД
        for idx, db_key in enumerate(db_types):
            print(f"Тестирование {db_key} со сценарием {scenario['name']}...")

            if self._metrics_callback:
                self._metrics_callback.set_current_query(idx + 1)

            await self._emit_status(
                "running",
                f"Тестирование {self.db_connection.get_connection_name(db_key)}: {scenario['name']} ({idx + 1}/{len(db_types)})"
            )

            stats = await self.run_scenario_test(
                db_key,
                scenario,
                iterations=iterations,
                virtual_users=virtual_users,
                auto_restore=True
            )

            all_results.append({
                'db_key': db_key,
                'db_type': stats.get('db_type'),
                'scenario': scenario['name'],
                'stats': stats
            })

        # Уведомляем о завершении
        if self._metrics_callback:
            total_transactions = sum(
                result.get('stats', {}).get('successful', 0)
                for result in all_results
            )
            summary = {
                'total_transactions': total_transactions,
                'overall_tps': total_transactions / len(db_types) if db_types else 0,
            }
            await self._metrics_callback.on_test_complete(summary)

        return all_results

    async def execute_scenario_query(
        self,
        db_key: str,
        sql_template: str,
        params_config: List[Dict],
        scenario_name: str
    ) -> Dict:
        """Выполнение запроса сценария с подстановкой параметров"""
        import random
        import uuid

        start_time = time.perf_counter()
        error = None
        rows_count = 0
        db_type = self.db_connection.get_dbms_type(db_key)

        # Подстановка параметров
        param_values = {}
        for param_config in params_config:
            param_name = param_config['param_name']
            param_type = param_config['param_type']
            param_values[param_name] = await self._generate_param_value(
                db_key, param_type, param_config
            )

        # Формируем финальный SQL
        try:
            final_sql = sql_template.format(**param_values)
        except KeyError as e:
            error = f"Missing parameter: {e}"
            final_sql = sql_template

        try:
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                result = await conn.execute(text(final_sql))
                rows_count = len(result.fetchall()) if result.returns_rows else 0
                await conn.commit()
        except Exception as e:
            error = str(e)

        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000

        return {
            'scenario': scenario_name,
            'db_key': db_key,
            'db_type': db_type,
            'sql': final_sql[:200] + '...' if len(final_sql) > 200 else final_sql,
            'execution_time_ms': execution_time,
            'rows_count': rows_count,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    async def _generate_param_value(
        self,
        db_key: str,
        param_type: str,
        param_config: Dict
    ) -> Any:
        """Генерация значения параметра"""
        import random
        import uuid
        from datetime import timedelta

        if param_type == 'random_int':
            min_val = param_config.get('min_value', 1)
            max_val = param_config.get('max_value', 1000)
            return random.randint(min_val, max_val)

        elif param_type == 'random_from_table':
            table = param_config.get('table_ref', '')
            column = param_config.get('column_ref', '')
            return await self._get_random_value_from_table(db_key, table, column)

        elif param_type == 'sequential_int':
            # Для sequential используем текущее время как seed
            return int(datetime.now().timestamp()) % 100000

        elif param_type == 'uuid':
            return str(uuid.uuid4())

        elif param_type == 'fixed':
            return param_config.get('fixed_value', '')

        elif param_type == 'random_string':
            length = param_config.get('string_length', 10)
            chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            return ''.join(random.choice(chars) for _ in range(length))

        elif param_type == 'random_date':
            days = random.randint(0, 3650)  # ~10 years
            base_date = datetime(2000, 1, 1)
            return (base_date + timedelta(days=days)).strftime('%Y-%m-%d')

        else:
            return 1  # Default fallback

    async def _get_random_value_from_table(
        self,
        db_key: str,
        table: str,
        column: str
    ) -> Any:
        """Получение случайного значения из таблицы"""
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                # PostgreSQL использует RANDOM(), MySQL использует RAND()
                order_func = "RANDOM()" if db_type == "postgresql" else "RAND()"
                result = await conn.execute(text(f"""
                    SELECT {column} FROM {table}
                    ORDER BY {order_func} LIMIT 1
                """))
                row = result.fetchone()
                return row[0] if row else 1
        except Exception as e:
            print(f"Error getting random value: {e}")
            return 1

    async def run_scenario_test(
        self,
        db_key: str,
        scenario: Dict,
        iterations: int = 10,
        virtual_users: int = 1,
        auto_restore: bool = True
    ) -> Dict:
        """Запуск теста на основе сценария с автовосстановлением БД"""
        import random

        queries = scenario.get('queries', [])
        if not queries:
            return {
                'scenario': scenario.get('name', 'unknown'),
                'db_key': db_key,
                'db_type': self.db_connection.get_dbms_type(db_key),
                'error': 'No queries in scenario',
                'successful': 0,
                'failed': 0
            }

        # Получаем SQL запросы для анализа
        sql_queries = [q['sql_template'] for q in queries]
        
        # Подготовка БД
        prepare_info = await self.prepare_database_for_test(
            db_key, sql_queries, auto_restore
        )

        results = []
        start_time = time.perf_counter()

        # Создаем взвешенный список запросов
        weighted_queries = []
        for query in queries:
            weight = query.get('weight', 1)
            for _ in range(weight):
                weighted_queries.append(query)

        last_emit_time = start_time
        recent_times = []
        recent_successful = 0
        recent_failed = 0

        try:
            for i in range(iterations):
                # Выбираем случайный запрос из взвешенного списка
                query = random.choice(weighted_queries)

                result = await self.execute_scenario_query(
                    db_key,
                    query['sql_template'],
                    query.get('params', []),
                    scenario.get('name', 'unknown')
                )
                results.append(result)

                if result['error'] is None:
                    recent_times.append(result['execution_time_ms'])
                    recent_successful += 1
                else:
                    recent_failed += 1

                # Потоковая отправка метрик
                current_time = time.perf_counter()
                if self._is_streaming and (current_time - last_emit_time) >= self._streaming_interval:
                    if recent_times:
                        avg_response_time = statistics.mean(recent_times)
                        tps = (recent_successful + recent_failed) / (current_time - last_emit_time)

                        await self._emit_metrics(
                            db_key=db_key,
                            response_time=avg_response_time,
                            tps=tps,
                            successful=recent_successful,
                            failed=recent_failed
                        )

                    recent_times = []
                    recent_successful = 0
                    recent_failed = 0
                    last_emit_time = current_time

                await asyncio.sleep(0.01)

            end_time = time.perf_counter()
            total_test_time = end_time - start_time
            
        finally:
            # Восстановление БД
            restore_info = await self.restore_database_after_test(
                db_key, prepare_info, auto_restore
            )

        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        successful_count = len(execution_times)
        failed_count = len(results) - len(execution_times)

        db_type = self.db_connection.get_dbms_type(db_key)

        stats = {
            'scenario': scenario.get('name', 'unknown'),
            'scenario_type': scenario.get('scenario_type', 'unknown'),
            'db_key': db_key,
            'db_type': db_type,
            'iterations': iterations,
            'virtual_users': virtual_users,
            'successful': successful_count,
            'failed': failed_count,
            'avg_time_ms': statistics.mean(execution_times) if execution_times else 0,
            'min_time_ms': min(execution_times) if execution_times else 0,
            'max_time_ms': max(execution_times) if execution_times else 0,
            'p50_time_ms': self.calculate_percentile(execution_times, 50) if execution_times else 0,
            'p95_time_ms': self.calculate_percentile(execution_times, 95) if execution_times else 0,
            'p99_time_ms': self.calculate_percentile(execution_times, 99) if execution_times else 0,
            'tps': successful_count / total_test_time if total_test_time > 0 else 0,
            'throughput': successful_count / total_test_time if total_test_time > 0 else 0,
            'error_rate': (failed_count / iterations) * 100 if iterations > 0 else 0,
            'restore_info': {
                'needed': prepare_info.get('needs_restore', False),
                'restored': restore_info.get('restored', False),
                'affected_tables': prepare_info.get('affected_tables', []),
                'duration_ms': restore_info.get('duration_ms'),
                'verified': restore_info.get('verified'),
                'errors': restore_info.get('errors')
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        return stats

    async def run_full_scenario_test_suite(
        self,
        scenario_id: str,
        db_types: List[str] = None,
        iterations: int = 100,
        virtual_users: int = 10,
        warmup_time: int = 5,
        scenario_repository = None
    ) -> List[Dict]:
        """Запуск полного теста на основе сценария из БД"""
        from backend.database.repository import ScenarioRepository

        if db_types is None:
            db_types = ['mysql', 'postgresql']

        # Загружаем сценарий - используем переданный репозиторий или создаем новый
        if scenario_repository is not None:
            scenario_repo = scenario_repository
        else:
            # Fallback: создаем репозиторий с дефолтным URL
            import os
            db_url = os.getenv('HISTORY_DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5433/test_history')
            scenario_repo = ScenarioRepository(db_url)
        
        scenario = await scenario_repo.get_scenario_for_execution(scenario_id)

        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        all_results = []

        # Устанавливаем количество БД для прогресса
        if self._metrics_callback:
            self._metrics_callback.set_total_queries(len(db_types))
            await self._metrics_callback.on_test_start()

        # Прогрев
        if warmup_time > 0:
            print(f"Прогрев системы ({warmup_time} сек)...")
            await self._emit_status("running", f"Прогрев системы ({warmup_time} сек)...")

            queries = scenario.get('queries', [])
            if queries:
                warmup_query = queries[0]
                for db_key in db_types:
                    for _ in range(min(5, iterations // 10)):
                        await self.execute_scenario_query(
                            db_key,
                            warmup_query['sql_template'],
                            warmup_query.get('params', []),
                            scenario['name']
                        )
                        await asyncio.sleep(0.1)
            await asyncio.sleep(warmup_time)

        # Запуск тестов для каждой БД
        for idx, db_key in enumerate(db_types):
            print(f"Тестирование {db_key} со сценарием {scenario['name']}...")

            if self._metrics_callback:
                self._metrics_callback.set_current_query(idx + 1)

            await self._emit_status(
                "running",
                f"Тестирование {self.db_connection.get_connection_name(db_key)}: {scenario['name']} ({idx + 1}/{len(db_types)})"
            )

            stats = await self.run_scenario_test(
                db_key,
                scenario,
                iterations=iterations,
                virtual_users=virtual_users,
                auto_restore=True
            )

            all_results.append({
                'db_key': db_key,
                'db_type': stats.get('db_type'),
                'scenario': scenario['name'],
                'stats': stats
            })

        # Уведомляем о завершении
        if self._metrics_callback:
            total_transactions = sum(
                result.get('stats', {}).get('successful', 0)
                for result in all_results
            )
            summary = {
                'total_transactions': total_transactions,
                'overall_tps': total_transactions / len(db_types) if db_types else 0,
            }
            await self._metrics_callback.on_test_complete(summary)

        return all_results

    async def close(self):
        """Закрытие подключений"""
        await self.db_connection.close_all()
    
    # ==================== Методы для backup/restore ====================
    
    async def prepare_database_for_test(
        self, 
        db_key: str, 
        queries: List[str],
        auto_restore: bool = True
    ) -> Dict:
        """
        Подготовка БД к тесту: анализ запросов и создание backup если нужно
        
        Args:
            db_key: Ключ подключения
            queries: Список SQL запросов
            auto_restore: Включить автовосстановление после теста
            
        Returns:
            Dict с результатами подготовки
        """
        needs_restore = self.state_manager.needs_restore(queries)
        
        if not needs_restore:
            return {
                "needs_restore": False,
                "affected_tables": [],
                "prepare_result": None
            }
        
        affected_tables = self.state_manager.get_affected_tables(queries)
        
        # Отправляем статус
        await self._emit_backup_status("backup_started", {
            "dbms_type": self.db_connection.get_dbms_type(db_key),
            "tables": list(affected_tables),
            "auto_restore": auto_restore
        })
        
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            prepare_result = await self.state_manager.prepare_for_test(
                engine, db_type, queries
            )
            
            # Отправляем статус о завершении backup
            await self._emit_backup_status("backup_completed", {
                "dbms_type": db_type,
                "tables": list(affected_tables),
                "row_counts": prepare_result.backup_info.row_counts if prepare_result.backup_info else {},
                "warnings": prepare_result.warnings
            })
            
            return {
                "needs_restore": True,
                "affected_tables": list(affected_tables),
                "prepare_result": prepare_result
            }
            
        except Exception as e:
            await self._emit_backup_status("backup_failed", {
                "dbms_type": self.db_connection.get_dbms_type(db_key),
                "error": str(e)
            })
            raise
    
    async def restore_database_after_test(
        self,
        db_key: str,
        prepare_result: Dict,
        auto_restore: bool = True
    ) -> Dict:
        """
        Восстановление БД после теста
        
        Args:
            db_key: Ключ подключения
            prepare_result: Результат подготовки (от prepare_database_for_test)
            auto_restore: Выполнить восстановление
            
        Returns:
            Dict с результатами восстановления
        """
        if not prepare_result.get("needs_restore") or not auto_restore:
            return {
                "restored": False,
                "reason": "No restore needed or auto_restore disabled"
            }
        
        await self._emit_backup_status("restore_started", {
            "dbms_type": self.db_connection.get_dbms_type(db_key),
            "tables": prepare_result.get("affected_tables", [])
        })
        
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            restore_result = await self.state_manager.restore_after_test(
                engine, db_type, prepare_result["prepare_result"]
            )
            
            await self._emit_backup_status("restore_completed", {
                "dbms_type": db_type,
                "success": restore_result.success,
                "duration_ms": restore_result.duration_ms,
                "verified": restore_result.verified,
                "errors": restore_result.errors
            })
            
            return {
                "restored": restore_result.success,
                "duration_ms": restore_result.duration_ms,
                "verified": restore_result.verified,
                "errors": restore_result.errors
            }
            
        except Exception as e:
            await self._emit_backup_status("restore_failed", {
                "dbms_type": self.db_connection.get_dbms_type(db_key),
                "error": str(e)
            })
            return {
                "restored": False,
                "error": str(e)
            }
