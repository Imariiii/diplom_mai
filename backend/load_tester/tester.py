"""
Модуль для проведения нагрузочного тестирования
"""
import time
import asyncio
import statistics
import psutil
import re
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone
from sqlalchemy import text
from backend.database.connection import DatabaseConnection
from backend.database.dialects import get_dialect
from backend.database.queries import QueryManager
from backend.database.state_manager import DatabaseStateManager
from backend.load_tester.index_manager import IndexManager
from backend.load_tester.self_check import cross_validate_metrics, verify_littles_law


class LoadTester:
    """Класс для проведения нагрузочного тестирования"""
    
    def __init__(self, connection_repo=None):
        self.db_connection = DatabaseConnection()
        if connection_repo:
            self.db_connection.set_connection_repository(connection_repo)
        self.query_manager = QueryManager()
        self.state_manager = DatabaseStateManager()
        self.index_manager = IndexManager()
        self.results: List[Dict] = []
        self.auto_restore: bool = True
        self._random_value_cache: Dict[str, List[Any]] = {}
        self._random_value_cache_locks: Dict[str, asyncio.Lock] = {}
        
        # Callback для real-time обновлений
        self._metrics_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        self._backup_callback: Optional[Callable] = None
        self._is_streaming: bool = False
        self._streaming_interval: float = 1.0
        
        psutil.cpu_percent(interval=None)
    
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

    def _build_random_value_cache_key(self, db_key: str, table: str, column: str) -> str:
        """Построить ключ кэша значений для random_from_table"""
        return f"{db_key}:{table}:{column}"
    
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
                
                system_metrics = await self.get_system_metrics(db_key)
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
    
    async def _run_workers(
        self,
        db_key: str,
        iterations: int,
        virtual_users: int,
        query_func: Callable,
        progress_start: Optional[float] = None,
        progress_end: Optional[float] = None,
    ) -> List[Dict]:
        """
        Запуск виртуальных пользователей для параллельного выполнения запросов.
        
        При virtual_users <= 1 выполнение последовательное (обратная совместимость).
        При virtual_>users 1 каждый воркер выполняет iterations запросов независимо
        (итого = iterations × virtual_users), создавая реальную конкурентную нагрузку.
        Пул соединений масштабируется автоматически.
        
        Args:
            db_key: Ключ подключения к БД
            iterations: Количество итераций на каждого виртуального пользователя
            virtual_users: Количество параллельных воркеров
            query_func: Async-функция без аргументов, возвращающая Dict с результатом
            progress_start: Начальное значение прогресса для фазы тестирования (0-100)
            progress_end: Конечное значение прогресса для фазы тестирования (0-100)
        """
        if virtual_users <= 1:
            results = []
            last_emit_time = time.perf_counter()
            recent_times = []
            recent_successful = 0
            recent_failed = 0
            
            for i in range(iterations):
                result = await query_func()
                results.append(result)
                
                if result['error'] is None:
                    recent_times.append(result['execution_time_ms'])
                    recent_successful += 1
                else:
                    recent_failed += 1
                
                # Обновляем прогресс по завершённым итерациям
                if (progress_start is not None and progress_end is not None
                        and self._metrics_callback and iterations > 0):
                    frac = (i + 1) / iterations
                    self._metrics_callback.set_progress(
                        progress_start + frac * (progress_end - progress_start)
                    )

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
            
            return results
        
        await self.db_connection.ensure_pool_size(db_key, virtual_users)
        
        psutil.cpu_percent(interval=None)
        
        results: List[Dict] = []
        results_lock = asyncio.Lock()
        metrics_state = {
            'recent_times': [],
            'recent_successful': 0,
            'recent_failed': 0,
            'total_completed': 0,
            'last_emit_time': time.perf_counter(),
        }
        
        async def worker(worker_id: int):
            for _ in range(iterations):
                result = await query_func()
                async with results_lock:
                    results.append(result)
                    if result['error'] is None:
                        metrics_state['recent_times'].append(result['execution_time_ms'])
                        metrics_state['recent_successful'] += 1
                    else:
                        metrics_state['recent_failed'] += 1
                    metrics_state['total_completed'] += 1
                await asyncio.sleep(0.001)
        
        total_iterations = virtual_users * iterations

        async def metrics_emitter():
            try:
                while True:
                    await asyncio.sleep(self._streaming_interval)
                    snapshot = None
                    completed_now = 0
                    async with results_lock:
                        now = time.perf_counter()
                        interval = now - metrics_state['last_emit_time']
                        if metrics_state['recent_times']:
                            snapshot = {
                                'avg_rt': statistics.mean(metrics_state['recent_times']),
                                'successful': metrics_state['recent_successful'],
                                'failed': metrics_state['recent_failed'],
                                'tps': (metrics_state['recent_successful'] + metrics_state['recent_failed']) / interval if interval > 0 else 0,
                            }
                        completed_now = metrics_state['total_completed']
                        metrics_state['recent_times'] = []
                        metrics_state['recent_successful'] = 0
                        metrics_state['recent_failed'] = 0
                        metrics_state['last_emit_time'] = now
                    # Обновляем прогресс по завершённым итерациям
                    if (progress_start is not None and progress_end is not None
                            and self._metrics_callback and total_iterations > 0):
                        frac = min(1.0, completed_now / total_iterations)
                        self._metrics_callback.set_progress(
                            progress_start + frac * (progress_end - progress_start)
                        )
                    if snapshot:
                        await self._emit_metrics(
                            db_key=db_key,
                            response_time=snapshot['avg_rt'],
                            tps=snapshot['tps'],
                            successful=snapshot['successful'],
                            failed=snapshot['failed'],
                        )
            except asyncio.CancelledError:
                return
        
        tasks = []
        for w in range(virtual_users):
            tasks.append(asyncio.create_task(worker(w)))
        
        emitter_task = asyncio.create_task(metrics_emitter()) if self._is_streaming else None
        
        await asyncio.gather(*tasks)
        
        if emitter_task:
            emitter_task.cancel()
            try:
                await emitter_task
            except asyncio.CancelledError:
                pass

            now = time.perf_counter()
            interval = now - metrics_state['last_emit_time']
            if metrics_state['recent_times'] or metrics_state['recent_successful'] or metrics_state['recent_failed']:
                avg_rt = statistics.mean(metrics_state['recent_times']) if metrics_state['recent_times'] else 0
                total_completed = metrics_state['recent_successful'] + metrics_state['recent_failed']
                final_tps = total_completed / interval if interval > 0 else total_completed
                await self._emit_metrics(
                    db_key=db_key,
                    response_time=avg_rt,
                    tps=final_tps,
                    successful=metrics_state['recent_successful'],
                    failed=metrics_state['recent_failed'],
                )
        
        return results
    
    def calculate_percentile(self, data: List[float], percentile: float) -> float:
        """Вычисление перцентиля"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def _build_self_check(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Сформировать блок самопроверки для рассчитанных метрик."""
        avg_time_ms = stats.get('avg_time_all_ms') or stats.get('avg_time_ms') or 0
        virtual_users = stats.get('virtual_users') or 0
        throughput = stats.get('completed_tps') or stats.get('throughput') or 0
        littles_law = verify_littles_law(
            virtual_users=int(virtual_users),
            avg_latency_sec=float(avg_time_ms) / 1000.0,
            throughput_rps=float(throughput),
        )
        warnings = cross_validate_metrics(stats)
        if littles_law.get('warning'):
            warnings.append(littles_law['warning'])

        return {
            'littles_law': littles_law,
            'warnings': warnings,
        }

    def build_metric_samples(
        self,
        results: List[Dict[str, Any]],
        db_key: str,
        query_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Преобразовать raw результаты выполнения в sample-метрики для БД истории.

        Generates both request_latency (one per request) and throughput_window
        (one per 1-second time bucket) records so that the comparison service
        has structured throughput data without falling back to aggregates.
        """
        db_type = self.db_connection.get_dbms_type(db_key)
        samples = []

        parsed_timestamps: List[datetime] = []

        for result in results:
            timestamp_raw = result.get('timestamp')
            timestamp = None

            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            elif isinstance(timestamp_raw, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_raw)
                except ValueError:
                    timestamp = datetime.now(timezone.utc)

            if timestamp is None:
                timestamp = datetime.now(timezone.utc)

            parsed_timestamps.append(timestamp)

            samples.append({
                'db_type': db_type,
                'connection_key': db_key,
                'query_id': query_id or result.get('query_id') or result.get('scenario'),
                'sample_type': 'request_latency',
                'timestamp': timestamp,
                'latency_ms': result.get('execution_time_ms'),
                'throughput': None,
                'tps': None,
                'is_error': result.get('error') is not None,
                'error_message': result.get('error'),
            })

        samples.extend(
            self._build_throughput_windows(
                results, parsed_timestamps, db_type, db_key, query_id,
            )
        )

        return samples

    @staticmethod
    def _build_throughput_windows(
        results: List[Dict[str, Any]],
        timestamps: List[datetime],
        db_type: str,
        db_key: str,
        query_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Aggregate request results into 1-second throughput windows."""
        if not timestamps:
            return []

        buckets: Dict[int, List[float]] = {}
        epoch_base = int(min(timestamps).timestamp())
        for ts, result in zip(timestamps, results):
            bucket = int(ts.timestamp()) - epoch_base
            latency = result.get('execution_time_ms')
            if latency is not None:
                buckets.setdefault(bucket, []).append(latency)

        if not buckets:
            return []

        window_samples = []
        for bucket_offset in sorted(buckets):
            latencies = buckets[bucket_offset]
            count = len(latencies)
            avg_latency = sum(latencies) / count if count else 0
            bucket_ts = datetime.fromtimestamp(
                epoch_base + bucket_offset, tz=timezone.utc
            )
            window_samples.append({
                'db_type': db_type,
                'connection_key': db_key,
                'query_id': query_id,
                'sample_type': 'throughput_window',
                'timestamp': bucket_ts,
                'latency_ms': avg_latency,
                'throughput': float(count),
                'tps': float(count),
                'is_error': False,
                'error_message': None,
            })

        return window_samples
    
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
        
        prepare_info = await self.prepare_database_for_test(
            db_key, queries, auto_restore
        )
        
        start_time = time.perf_counter()
        
        try:
            async def _make_query():
                return await self.execute_query(db_key, query['sql'], query_id)
            
            results = await self._run_workers(
                db_key=db_key,
                iterations=iterations,
                virtual_users=virtual_users,
                query_func=_make_query,
            )
            
            end_time = time.perf_counter()
            total_test_time = end_time - start_time
            
        finally:
            restore_info = await self.restore_database_after_test(
                db_key, prepare_info, auto_restore
            )
        
        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        all_execution_times = [
            r['execution_time_ms']
            for r in results
            if r.get('execution_time_ms') is not None
        ]
        
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
                'avg_time_all_ms': statistics.mean(all_execution_times) if all_execution_times else 0,
                'completed_tps': len(results) / total_test_time if total_test_time > 0 else 0,
                
                # TPS (Транзакций в секунду)
                'tps': successful_count / total_test_time if total_test_time > 0 else 0,
                'throughput': successful_count / total_test_time if total_test_time > 0 else 0,
                
                # Активные соединения
                'active_connections': virtual_users,
                
                # Количество ошибок
                'error_count': failed_count,
                'error_rate': (failed_count / len(results)) * 100 if len(results) > 0 else 0,
                
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
                'avg_time_all_ms': statistics.mean(all_execution_times) if all_execution_times else 0,
                'completed_tps': len(results) / total_test_time if total_test_time > 0 else 0,
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
        
        stats['self_check'] = self._build_self_check(stats)
        stats['raw_samples'] = self.build_metric_samples(results, db_key, query_id=query_id)
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
            remaining = warmup_time
            while remaining > 0:
                await self._emit_status(
                    "running",
                    f"Прогрев системы, осталось {remaining} с…",
                )
                step = min(1, remaining)
                await asyncio.sleep(step)
                remaining -= step
            await self._emit_status(
                "running",
                "Запуск нагрузочного теста по набору запросов…",
            )

        for idx, query in enumerate(queries):
            print(f"Тестирование запроса: {query['name']} ({idx + 1}/{total_queries})")
            
            await self._emit_status("running", f"Тестирование: {query['name']} ({idx + 1}/{total_queries})")
            
            comparison = await self.run_comparison_test(
                query['id'],
                db_types,
                iterations,
                virtual_users=virtual_users,
                scenario=scenario
            )
            all_results.append(comparison)
            
            # Обновляем прогресс после завершения каждого запроса
            if self._metrics_callback:
                self._metrics_callback.set_current_query(idx + 1)

        return all_results
    
    async def run_custom_sql_test(
        self,
        custom_sql: str,
        db_types: List[str],
        iterations: int = 10,
        virtual_users: int = 10,
        warmup_time: int = 5,
    ) -> List[Dict]:
        """Run a load test using a user-provided SQL query."""
        query_id = "custom_sql"
        query_entry = {
            "id": query_id,
            "name": "Пользовательский SQL",
            "sql": custom_sql,
            "description": "Пользовательский SQL-запрос",
        }

        total_dbs = len(db_types)
        if self._metrics_callback:
            await self._metrics_callback.on_test_start()

        def _set_prog(value: float):
            if self._metrics_callback:
                self._metrics_callback.set_progress(max(0.0, min(100.0, value)))

        # Фаза: прогрев (0-8%)
        if warmup_time > 0:
            _set_prog(0.0)
            print(f"Прогрев системы ({warmup_time} сек)...")
            await self._emit_status("running", f"Прогрев системы ({warmup_time} сек)...")
            for db_key in db_types:
                for _ in range(min(3, iterations)):
                    await self.execute_query(db_key, custom_sql, query_id)
                    await asyncio.sleep(0.05)
            remaining = warmup_time
            while remaining > 0:
                await self._emit_status(
                    "running",
                    f"Прогрев системы, осталось {remaining} с…",
                )
                step = min(1, remaining)
                await asyncio.sleep(step)
                remaining -= step
            _set_prog(8.0)

        await self._emit_status(
            "running",
            "Подготовка баз данных к нагрузочному тесту…",
        )

        results: Dict[str, Dict] = {}
        prepare_infos: Dict[str, Dict] = {}

        # Фаза: подготовка / backup всех БД (0-8% или продолжение после прогрева)
        prepare_start = 8.0 if warmup_time > 0 else 0.0
        prepare_end = prepare_start + 8.0
        for prep_idx, db_key in enumerate(db_types):
            print(f"Подготовка {db_key}...")
            _set_prog(prepare_start + (prep_idx / total_dbs) * (prepare_end - prepare_start))
            prepare_info = await self.prepare_database_for_test(
                db_key, [custom_sql], self.auto_restore
            )
            prepare_infos[db_key] = prepare_info
        _set_prog(prepare_end)

        # Фаза: тестирование (prepare_end-92%), каждая БД получает равный срез
        test_range_start = prepare_end
        test_range_end = 92.0
        test_slice = (test_range_end - test_range_start) / total_dbs if total_dbs > 0 else 0

        try:
            for db_idx, db_key in enumerate(db_types):
                db_prog_start = test_range_start + db_idx * test_slice
                db_prog_end = test_range_start + (db_idx + 1) * test_slice

                print(f"Тестирование {db_key} ({db_idx + 1}/{total_dbs})...")
                await self._emit_status("running", f"Тестирование: пользовательский SQL ({db_idx + 1}/{total_dbs})")
                _set_prog(db_prog_start)

                async def _make_query(dk=db_key):
                    return await self.execute_query(dk, custom_sql, query_id)

                run_results = await self._run_workers(
                    db_key=db_key,
                    iterations=iterations,
                    virtual_users=virtual_users,
                    query_func=_make_query,
                    progress_start=db_prog_start,
                    progress_end=db_prog_end,
                )

                _set_prog(db_prog_end)

                execution_times = [r["execution_time_ms"] for r in run_results if r["error"] is None]
                all_execution_times = [
                    r["execution_time_ms"]
                    for r in run_results
                    if r.get("execution_time_ms") is not None
                ]
                total_test_time = sum(r["execution_time_ms"] for r in run_results) / 1000.0 if run_results else 0
                db_type = self.db_connection.get_dbms_type(db_key)

                if execution_times:
                    successful = len(execution_times)
                    failed = len(run_results) - successful
                    stats = {
                        "query_id": query_id,
                        "db_key": db_key,
                        "db_type": db_type,
                        "iterations": iterations,
                        "virtual_users": virtual_users,
                        "scenario": "custom",
                        "successful": successful,
                        "failed": failed,
                        "avg_time_ms": statistics.mean(execution_times),
                        "min_time_ms": min(execution_times),
                        "max_time_ms": max(execution_times),
                        "p50_time_ms": self.calculate_percentile(execution_times, 50),
                        "p95_time_ms": self.calculate_percentile(execution_times, 95),
                        "p99_time_ms": self.calculate_percentile(execution_times, 99),
                        "total_time_ms": sum(execution_times),
                        "std_dev_ms": statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
                        "avg_time_all_ms": statistics.mean(all_execution_times) if all_execution_times else 0,
                        "completed_tps": len(run_results) / total_test_time if total_test_time > 0 else 0,
                        "tps": successful / total_test_time if total_test_time > 0 else 0,
                        "throughput": successful / total_test_time if total_test_time > 0 else 0,
                        "active_connections": virtual_users,
                        "error_count": failed,
                        "error_rate": (failed / len(run_results)) * 100 if run_results else 0,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    stats = {
                        "query_id": query_id,
                        "db_key": db_key,
                        "db_type": db_type,
                        "iterations": iterations,
                        "virtual_users": virtual_users,
                        "scenario": "custom",
                        "successful": 0,
                        "failed": len(run_results),
                        "error": "Все запросы завершились с ошибкой",
                        "tps": 0,
                        "throughput": 0,
                        "avg_time_all_ms": statistics.mean(all_execution_times) if all_execution_times else 0,
                        "completed_tps": len(run_results) / total_test_time if total_test_time > 0 else 0,
                        "active_connections": virtual_users,
                        "error_count": len(run_results),
                        "error_rate": 100,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                stats["self_check"] = self._build_self_check(stats)
                stats["raw_samples"] = self.build_metric_samples(run_results, db_key, query_id=query_id)
                results[db_key] = stats

        finally:
            # Фаза: восстановление всех БД (92-100%)
            restore_dbs = [k for k in db_types if prepare_infos.get(k, {}).get("needs_restore")]
            n_restore = len(restore_dbs)
            for rest_idx, db_key in enumerate(restore_dbs):
                _set_prog(92.0 + (rest_idx / n_restore) * 8.0 if n_restore > 0 else 92.0)
                await self.restore_database_after_test(
                    db_key, prepare_infos[db_key], self.auto_restore
                )
            _set_prog(100.0)

        return [
            {
                "query_id": query_id,
                "comparison": results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

    async def get_system_metrics(self, db_key: str) -> Dict:
        """Получить системные метрики"""
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
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
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            dialect = get_dialect(db_type)
            async with engine.connect() as conn:
                return await dialect.collect_dbms_metrics(conn)
        except Exception as e:
            print(f"Ошибка получения метрик СУБД {db_key}: {e}")

        return {
            'cache_hit_ratio': 0,
            'buffer_pool_hit_ratio': 0,
            'lock_waits': 0,
            'lock_waits_mode': 'current',
            'deadlocks': 0,
            'deadlocks_mode': 'current',
            'active_connections': 0,
            'table_sizes_mb': {},
            'index_sizes_mb': {},
            'total_db_size_mb': 0,
        }

    async def get_dbms_metric_counters(self, db_key: str) -> Dict:
        """Получить накопительные счётчики СУБД для расчёта delta за прогон."""
        try:
            db_type = self.db_connection.get_dbms_type(db_key)
            engine = await self.db_connection.get_engine_async(db_key)
            dialect = get_dialect(db_type)
            async with engine.connect() as conn:
                return await dialect.collect_dbms_metric_counters(conn)
        except Exception as e:
            print(f"Ошибка получения счётчиков СУБД {db_key}: {e}")
            return {}

    def build_final_dbms_metrics(
        self,
        db_key: str,
        latest_metrics: Dict[str, Any],
        start_counters: Dict[str, Any],
        end_counters: Dict[str, Any],
        runtime_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Сформировать финальные внутренние метрики СУБД для отчёта."""
        db_type = self.db_connection.get_dbms_type(db_key)
        dialect = get_dialect(db_type)
        return dialect.build_final_dbms_metrics(
            latest_metrics=latest_metrics,
            start_counters=start_counters,
            end_counters=end_counters,
            runtime_stats=runtime_stats,
        )
    
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
        try:
            for param_config in params_config:
                param_name = param_config['param_name']
                param_type = param_config['param_type']
                param_values[param_name] = await self._generate_param_value(
                    db_key, param_type, param_config
                )
        except Exception as e:
            error = str(e)

        final_sql = sql_template
        if error is None:
            try:
                executable_sql = self._build_executable_sql(sql_template, param_values)
            except KeyError as e:
                error = f"Missing parameter: {e}"
                executable_sql = text(sql_template)
        else:
            executable_sql = text(sql_template)

        try:
            if error is not None:
                raise RuntimeError(error)
            engine = await self.db_connection.get_engine_async(db_key)
            async with engine.connect() as conn:
                result = await conn.execute(executable_sql, param_values)
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
            raise ValueError(f"Неизвестный тип параметра: {param_type}")

    async def _get_random_value_from_table(
        self,
        db_key: str,
        table: str,
        column: str
    ) -> Any:
        """Получение случайного значения из таблицы с кэшированием на время теста"""
        import random

        cache_key = self._build_random_value_cache_key(db_key, table, column)
        cached_values = self._random_value_cache.get(cache_key)
        if cached_values:
            return random.choice(cached_values)

        lock = self._random_value_cache_locks.setdefault(cache_key, asyncio.Lock())
        try:
            async with lock:
                cached_values = self._random_value_cache.get(cache_key)
                if cached_values:
                    return random.choice(cached_values)

                db_type = self.db_connection.get_dbms_type(db_key)
                dialect = get_dialect(db_type)
                engine = await self.db_connection.get_engine_async(db_key)
                async with engine.connect() as conn:
                    result = await conn.execute(
                        text(dialect.get_sample_column_values_sql(table, column)),
                        {"limit": 1000},
                    )
                    values = [row[0] for row in result.fetchall() if row[0] is not None]

                self._random_value_cache[cache_key] = values
                if values:
                    return random.choice(values)
                raise ValueError(f"Нет значений для параметра {table}.{column}")
        except Exception as e:
            print(f"Error getting random value: {e}")
            raise

    def _build_executable_sql(self, sql_template: str, param_values: Dict[str, Any]):
        """Преобразовать template-плейсхолдеры в bind parameters SQLAlchemy."""
        executable_sql = sql_template
        for param_name in sorted(param_values.keys(), key=len, reverse=True):
            executable_sql = executable_sql.replace("'{" + param_name + "}'", f":{param_name}")
            executable_sql = executable_sql.replace("{" + param_name + "}", f":{param_name}")
        missing = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", executable_sql)
        if missing:
            raise KeyError(", ".join(sorted(set(missing))))
        return text(executable_sql)

    async def _prime_random_value_cache(self, db_key: str, queries: List[Dict[str, Any]]):
        """Предзагрузить значения для random_from_table до запуска воркеров"""
        refs = []
        seen = set()

        for query in queries:
            for param in query.get('params', []):
                if param.get('param_type') != 'random_from_table':
                    continue
                table = param.get('table_ref')
                column = param.get('column_ref')
                if not table or not column:
                    continue
                key = (table, column)
                if key in seen:
                    continue
                seen.add(key)
                refs.append(key)

        for table, column in refs:
            await self._get_random_value_from_table(db_key, table, column)

    async def run_scenario_test(
        self,
        db_key: str,
        scenario: Dict,
        iterations: int = 10,
        virtual_users: int = 1,
        auto_restore: bool = True,
        warmup_time: int = 0,
        use_indexes: bool = False,
        progress_start: float = 0.0,
        progress_end: float = 100.0,
    ) -> Dict:
        """Запуск теста на основе сценария с автовосстановлением БД"""
        import random

        conn_name = self.db_connection.get_connection_name(db_key)
        scenario_name = scenario.get('name', 'unknown')

        # Вспомогательная функция для установки прогресса в пределах выделенного диапазона
        _pslice = progress_end - progress_start
        def _set_progress(pct: float):
            if self._metrics_callback:
                self._metrics_callback.set_progress(progress_start + _pslice * pct)

        queries = scenario.get('queries', [])
        scenario_indexes = scenario.get('indexes', [])
        if not queries:
            print(f"[SCENARIO] ⚠ Нет запросов в сценарии {scenario_name!r} для {conn_name}")
            return {
                'scenario': scenario_name,
                'db_key': db_key,
                'db_type': self.db_connection.get_dbms_type(db_key),
                'error': 'No queries in scenario',
                'successful': 0,
                'failed': 0
            }

        print(
            f"[SCENARIO] Старт {conn_name} | сценарий={scenario_name!r} | "
            f"{iterations} итер. x {virtual_users} VU | restore={auto_restore} | indexes={use_indexes}"
        )

        sql_queries = [q['sql_template'] for q in queries]

        # Фаза: подготовка / backup (0-8% диапазона)
        _set_progress(0.0)
        prepare_info = await self.prepare_database_for_test(
            db_key, sql_queries, auto_restore
        )
        _set_progress(0.08)

        weighted_queries = []
        for query in queries:
            weight = query.get('weight', 1)
            for _ in range(weight):
                weighted_queries.append(query)

        created_indexes: List[Dict[str, Any]] = []
        index_creation_result = None
        index_drop_result = None

        index_info = {
            'enabled': bool(use_indexes),
            'indexes_count': len(scenario_indexes) if use_indexes else 0,
            'total_creation_time_ms': 0.0,
            'drop_time_ms': 0.0,
            'details': [],
            'drop_details': [],
            'errors': [],
            'drop_errors': [],
        }

        try:
            if use_indexes and scenario_indexes:
                db_type = self.db_connection.get_dbms_type(db_key)
                engine = await self.db_connection.get_engine_async(db_key)

                print(f"[SCENARIO] Создание {len(scenario_indexes)} индексов для {conn_name}...")
                await self._emit_backup_status("index_creation_started", {
                    "dbms_type": db_type,
                    "indexes_count": len(scenario_indexes),
                    "indexes": scenario_indexes,
                })

                index_creation_result = await self.index_manager.create_indexes(
                    engine=engine,
                    db_type=db_type,
                    indexes=scenario_indexes,
                    callback=self._emit_backup_status,
                )
                index_info['total_creation_time_ms'] = index_creation_result.total_time_ms
                index_info['details'] = [detail.to_dict() for detail in index_creation_result.details]
                index_info['errors'] = index_creation_result.errors
                created_indexes = [
                    {
                        **index_def,
                        'index_name': detail.name,
                    }
                    for index_def, detail in zip(scenario_indexes, index_creation_result.details)
                    if detail.success and not detail.skipped
                ]

                await self._emit_backup_status("index_creation_completed", {
                    "dbms_type": db_type,
                    "success": index_creation_result.success,
                    "duration_ms": index_creation_result.total_time_ms,
                    "details": index_info['details'],
                    "errors": index_creation_result.errors,
                })

                if not index_creation_result.success:
                    print(f"[SCENARIO] Ошибка создания индексов для {conn_name}: {index_creation_result.errors}")
                    raise RuntimeError(
                        "Не удалось создать индексы: " + "; ".join(index_creation_result.errors)
                    )

                print(
                    f"[SCENARIO] Индексы созданы для {conn_name} "
                    f"за {index_creation_result.total_time_ms:.0f}ms"
                )

            await self._prime_random_value_cache(db_key, queries)

            # Фаза: прогрев (8-15% диапазона, если включён)
            if warmup_time > 0:
                warmup_iterations = max(1, min(5, max(1, iterations // 10)))
                print(f"[SCENARIO] Прогрев {conn_name}: {warmup_iterations} итер. + {warmup_time}s пауза...")
                await self._emit_status(
                    "running",
                    f"Прогрев сценария {scenario_name} ({warmup_time} сек)..."
                )
                for _ in range(warmup_iterations):
                    q = random.choice(weighted_queries)
                    await self.execute_scenario_query(
                        db_key,
                        q['sql_template'],
                        q.get('params', []),
                        scenario_name
                    )
                    await asyncio.sleep(0.1)
                remaining = warmup_time
                while remaining > 0:
                    await self._emit_status(
                        "running",
                        f"Прогрев сценария «{scenario_name}», осталось {remaining} с…",
                    )
                    step = min(1, remaining)
                    await asyncio.sleep(step)
                    remaining -= step
                print(f"[SCENARIO] Прогрев {conn_name} завершён")
                _set_progress(0.15)

            # Фаза: нагрузочное тестирование (15-88% с прогревом, 8-88% без)
            testing_start_pct = 0.15 if warmup_time > 0 else 0.08
            _set_progress(testing_start_pct)
            print(f"[SCENARIO] Запуск нагрузки {conn_name}: {iterations} итераций x {virtual_users} VU...")
            await self._emit_status(
                "running",
                f"Нагрузка: «{scenario_name}» — выполнение запросов "
                f"({iterations} ит. × {virtual_users} VU)…",
            )
            start_time = time.perf_counter()

            async def _make_scenario_query():
                q = random.choice(weighted_queries)
                return await self.execute_scenario_query(
                    db_key,
                    q['sql_template'],
                    q.get('params', []),
                    scenario_name
                )
            
            results = await self._run_workers(
                db_key=db_key,
                iterations=iterations,
                virtual_users=virtual_users,
                query_func=_make_scenario_query,
                progress_start=progress_start + _pslice * testing_start_pct,
                progress_end=progress_start + _pslice * 0.88,
            )

            end_time = time.perf_counter()
            total_test_time = end_time - start_time
            print(f"[SCENARIO] Нагрузка {conn_name} завершена за {total_test_time:.2f}с")
            _set_progress(0.88)
            
        finally:
            if created_indexes:
                print(f"[SCENARIO] Удаление {len(created_indexes)} индексов для {conn_name}...")
                try:
                    db_type = self.db_connection.get_dbms_type(db_key)
                    engine = await self.db_connection.get_engine_async(db_key)
                    await self._emit_backup_status("index_drop_started", {
                        "dbms_type": db_type,
                        "indexes_count": len(created_indexes),
                    })
                    index_drop_result = await self.index_manager.drop_indexes(
                        engine=engine,
                        db_type=db_type,
                        indexes=created_indexes,
                        callback=self._emit_backup_status,
                    )
                    index_info['drop_time_ms'] = index_drop_result.total_time_ms
                    index_info['drop_details'] = [detail.to_dict() for detail in index_drop_result.details]
                    index_info['drop_errors'] = index_drop_result.errors
                    await self._emit_backup_status("index_drop_completed", {
                        "dbms_type": db_type,
                        "success": index_drop_result.success,
                        "duration_ms": index_drop_result.total_time_ms,
                        "details": index_info['drop_details'],
                        "errors": index_drop_result.errors,
                    })
                    print(
                        f"[SCENARIO] Индексы удалены для {conn_name} "
                        f"за {index_drop_result.total_time_ms:.0f}ms"
                    )
                except Exception as e:
                    print(f"[SCENARIO] Ошибка удаления индексов для {conn_name}: {e}")
                    index_info['drop_errors'].append(str(e))
                    await self._emit_backup_status("index_drop_failed", {
                        "dbms_type": self.db_connection.get_dbms_type(db_key),
                        "error": str(e),
                    })
            # Фаза: восстановление БД (88-100% диапазона)
            _set_progress(0.88)
            restore_info = await self.restore_database_after_test(
                db_key, prepare_info, auto_restore
            )
            _set_progress(1.0)

        # Статистика
        execution_times = [r['execution_time_ms'] for r in results if r['error'] is None]
        all_execution_times = [
            r['execution_time_ms']
            for r in results
            if r.get('execution_time_ms') is not None
        ]
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
            'total_time_ms': sum(execution_times) if execution_times else 0,
            'std_dev_ms': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            'avg_time_all_ms': statistics.mean(all_execution_times) if all_execution_times else 0,
            'completed_tps': len(results) / total_test_time if total_test_time > 0 else 0,
            'tps': successful_count / total_test_time if total_test_time > 0 else 0,
            'throughput': successful_count / total_test_time if total_test_time > 0 else 0,
            'error_rate': (failed_count / len(results)) * 100 if len(results) > 0 else 0,
            'restore_info': {
                'needed': prepare_info.get('needs_restore', False),
                'restored': restore_info.get('restored', False),
                'affected_tables': prepare_info.get('affected_tables', []),
                'duration_ms': restore_info.get('duration_ms'),
                'verified': restore_info.get('verified'),
                'errors': restore_info.get('errors')
            },
            'index_info': index_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        stats['self_check'] = self._build_self_check(stats)
        stats['raw_samples'] = self.build_metric_samples(
            results,
            db_key,
            query_id=f"scenario:{scenario_name}"
        )

        print(
            f"[SCENARIO] ✓ {conn_name}: успешно={successful_count}, ошиб.={failed_count}, "
            f"avg={stats['avg_time_ms']:.1f}ms, p95={stats['p95_time_ms']:.1f}ms, "
            f"TPS={stats['tps']:.1f}"
        )
        return stats

    async def run_resolved_scenario_test_suite(
        self,
        scenario: Dict,
        db_types: List[str] = None,
        iterations: int = 100,
        virtual_users: int = 10,
        warmup_time: int = 5,
        use_indexes: bool = False,
    ) -> List[Dict]:
        """Запуск полного теста на основе уже разрешённого SQL-bundle/сценария."""
        if db_types is None:
            db_types = ['mysql', 'postgresql']

        all_results = []

        queries_count = len(scenario.get('queries', []))
        print(
            f"[TEST] Сценарий: {scenario['name']!r} | БД: {len(db_types)} | "
            f"итераций: {iterations} | VU: {virtual_users} | запросов в сценарии: {queries_count}"
        )

        if self._metrics_callback:
            await self._metrics_callback.on_test_start()

        n_dbs = len(db_types)

        # Запуск тестов для каждой БД с фазовым прогрессом
        for idx, db_key in enumerate(db_types):
            conn_name = self.db_connection.get_connection_name(db_key)
            print(f"Тестирование {db_key} ({conn_name}) со сценарием {scenario['name']}... ({idx + 1}/{n_dbs})")
            queries_in_scenario = scenario.get('queries', [])
            for q in queries_in_scenario:
                q_type = q.get('query_type', '—')
                q_sql = q.get('sql_template', '').strip().replace('\n', ' ')
                print(f"  [SQL] {q_type}: {q_sql}")

            p_start = idx / n_dbs * 100
            p_end = (idx + 1) / n_dbs * 100

            await self._emit_status(
                "running",
                f"Тестирование {self.db_connection.get_connection_name(db_key)}: {scenario['name']} ({idx + 1}/{n_dbs})"
            )

            stats = await self.run_scenario_test(
                db_key,
                scenario,
                iterations=iterations,
                virtual_users=virtual_users,
                auto_restore=self.auto_restore,
                warmup_time=warmup_time,
                use_indexes=use_indexes,
                progress_start=p_start,
                progress_end=p_end,
            )

            successful = stats.get('successful', 0)
            failed = stats.get('failed', 0)
            total = successful + failed
            avg_ms = stats.get('avg_time_ms', 0)
            tps = stats.get('tps', 0)
            print(
                f"[TEST] ✓ {conn_name}: {successful}/{total} успешно, "
                f"avg={avg_ms:.1f}ms, TPS={tps:.1f}"
            )

            all_results.append({
                'db_key': db_key,
                'db_type': stats.get('db_type'),
                'scenario': scenario['name'],
                'stats': stats
            })

        total_transactions = sum(
            result.get('stats', {}).get('successful', 0)
            for result in all_results
        )
        print(f"[TEST] Все БД протестированы. Итого успешных транзакций: {total_transactions}")

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
        conn_name = self.db_connection.get_connection_name(db_key)
        needs_restore = self.state_manager.needs_restore(queries)
        
        if not needs_restore:
            print(f"[DB] {conn_name}: backup не нужен (нет write-запросов)")
            return {
                "needs_restore": False,
                "affected_tables": [],
                "prepare_result": None
            }
        
        affected_tables = self.state_manager.get_affected_tables(queries)
        print(f"[DB] {conn_name}: backup запущен, таблицы: {sorted(affected_tables)}")
        
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
            print(f"[DB] {conn_name}: backup завершён")
            
            return {
                "needs_restore": True,
                "affected_tables": list(affected_tables),
                "prepare_result": prepare_result
            }
            
        except Exception as e:
            print(f"[DB] {conn_name}: backup завершился с ошибкой: {e}")
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
        conn_name = self.db_connection.get_connection_name(db_key)

        if not prepare_result.get("needs_restore"):
            print(f"[DB] {conn_name}: восстановление пропущено (backup не создавался)")
            return {
                "restored": False,
                "reason": "No restore needed or auto_restore disabled"
            }

        if not auto_restore:
            print(f"[DB] {conn_name}: восстановление пропущено (auto_restore=False)")
            return {
                "restored": False,
                "reason": "No restore needed or auto_restore disabled"
            }
        
        print(f"[DB] {conn_name}: восстановление запущено...")
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
            print(
                f"[DB] {conn_name}: восстановление завершено за {restore_result.duration_ms:.0f}ms"
                + (f", verified={restore_result.verified}" if restore_result.verified is not None else "")
            )
            
            return {
                "restored": restore_result.success,
                "duration_ms": restore_result.duration_ms,
                "verified": restore_result.verified,
                "errors": restore_result.errors
            }
            
        except Exception as e:
            print(f"[DB] {conn_name}: ошибка восстановления: {e}")
            await self._emit_backup_status("restore_failed", {
                "dbms_type": self.db_connection.get_dbms_type(db_key),
                "error": str(e)
            })
            return {
                "restored": False,
                "error": str(e)
            }
