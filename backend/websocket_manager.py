"""
WebSocket менеджер для real-time обновлений тестирования
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Any, Optional, Callable, Tuple
from fastapi import WebSocket
from dataclasses import dataclass, asdict


@dataclass
class TestMetricsUpdate:
    """Структура данных для обновления метрик теста"""
    test_id: str
    db_key: str
    db_type: str
    db_name: str = ""  # Имя подключения для отображения в UI
    timestamp: str = ""
    
    # Метрики производительности (realtime: attempt_rate — запросов SQL/с за окно)
    response_time: float = 0.0
    attempt_rate: float = 0.0
    active_connections: int = 0
    error_count: int = 0
    
    # Системные метрики
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_usage_mb: float = 0.0
    disk_iops: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    
    # Внутренние метрики СУБД
    cache_hit_ratio: Optional[float] = None
    buffer_pool_hit_ratio: Optional[float] = None
    cache_hit_ratio_status: Optional[str] = None
    cache_hit_ratio_note: Optional[str] = None
    cache_hit_ratio_mode: Optional[str] = None
    lock_waits: int = 0
    deadlocks: int = 0
    
    # Прогресс
    progress: float = 0.0  # 0-100
    elapsed_seconds: int = 0
    remaining_seconds: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class TestStatusUpdate:
    """Структура данных для обновления статуса теста"""
    test_id: str
    status: str  # pending, running, completed, failed
    message: Optional[str] = None
    progress: float = 0.0
    elapsed_seconds: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConnectionManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        # Словарь: test_id -> список WebSocket соединений
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Все активные соединения (для широковещательных сообщений)
        self.all_connections: Set[WebSocket] = set()
        # Callback для уведомления о новых подключениях
        self.on_connect_callback: Optional[Callable] = None
    
    async def connect(self, websocket: WebSocket, test_id: str = "global"):
        """Принять новое WebSocket соединение"""
        await websocket.accept()
        
        if test_id not in self.active_connections:
            self.active_connections[test_id] = []
        
        self.active_connections[test_id].append(websocket)
        self.all_connections.add(websocket)
        
        print(f"[WS] Новое соединение для теста {test_id}. Всего: {len(self.all_connections)}")
        
        # Отправляем приветственное сообщение
        await self.send_personal_message({
            "type": "connected",
            "test_id": test_id,
            "message": "Подключение установлено"
        }, websocket)
    
    def disconnect(self, websocket: WebSocket, test_id: str = "global"):
        """Отключить WebSocket соединение"""
        if test_id in self.active_connections:
            if websocket in self.active_connections[test_id]:
                self.active_connections[test_id].remove(websocket)
            
            # Удаляем пустые списки
            if not self.active_connections[test_id]:
                del self.active_connections[test_id]
        
        self.all_connections.discard(websocket)
        print(f"[WS] Соединение закрыто для теста {test_id}. Всего: {len(self.all_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Отправить сообщение конкретному клиенту"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WS] Ошибка отправки сообщения: {e}")
    
    async def broadcast_to_test(self, test_id: str, message: Dict[str, Any]):
        """Отправить сообщение всем подписчикам теста"""
        if test_id not in self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections[test_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Ошибка broadcast: {e}")
                disconnected.append(connection)
        
        # Удаляем отключившихся
        for conn in disconnected:
            self.disconnect(conn, test_id)
    
    async def broadcast_all(self, message: Dict[str, Any]):
        """Отправить сообщение всем подключенным клиентам"""
        disconnected = []
        for connection in self.all_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Ошибка broadcast_all: {e}")
                disconnected.append(connection)
        
        # Удаляем отключившихся
        for conn in disconnected:
            self.all_connections.discard(conn)
    
    async def send_metrics_update(self, update: TestMetricsUpdate):
        """Отправить обновление метрик"""
        message = {
            "type": "metrics",
            "data": update.to_dict()
        }
        await self.broadcast_to_test(update.test_id, message)
    
    async def send_status_update(self, update: TestStatusUpdate):
        """Отправить обновление статуса"""
        message = {
            "type": "status",
            "data": update.to_dict()
        }
        await self.broadcast_to_test(update.test_id, message)
        # Также отправляем в глобальный канал
        await self.broadcast_to_test("global", message)
    
    async def send_backup_status(
        self,
        test_id: str,
        status: str,
        data: Dict[str, Any],
        elapsed_seconds: int = 0,
    ):
        """
        Отправить статус backup/restore или index-операции
        
        Args:
            test_id: ID теста
            status: Тип статуса (backup_started, restore_completed, index_creation_started, etc.)
            data: Данные статуса (tables, duration_ms, verified, etc.)
            elapsed_seconds: Секунд с начала теста (on_test_start)
        """
        message = {
            "type": "backup_status",
            "status": status,
            "test_id": test_id,
            "elapsed_seconds": max(0, int(elapsed_seconds)),
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_test(test_id, message)
        # Также отправляем в глобальный канал
        await self.broadcast_to_test("global", message)

    async def send_operation_status(
        self,
        test_id: str,
        status: str,
        data: Dict[str, Any],
        elapsed_seconds: int = 0,
    ):
        """Совместимый алиас для статусов служебных операций теста"""
        await self.send_backup_status(test_id, status, data, elapsed_seconds=elapsed_seconds)
    
    def get_connection_count(self, test_id: str = None) -> int:
        """Получить количество соединений"""
        if test_id:
            return len(self.active_connections.get(test_id, []))
        return len(self.all_connections)


# Глобальный менеджер соединений
manager = ConnectionManager()


class TestStreamingCallback:
    """
    Callback для потоковой отправки метрик из LoadTester в WebSocket
    """
    
    def __init__(self, test_id: str, connection_manager: ConnectionManager, repository=None):
        self.test_id = test_id
        self.manager = connection_manager
        self.repository = repository
        self.start_time = time.perf_counter()
        self.total_queries = 1  # Общее количество запросов для расчёта шагового прогресса
        self.current_query = 0  # Текущий обрабатываемый запрос (для шагового прогресса)
        self._progress: float = 0.0  # Прямое значение прогресса (0-100)
        self.metrics_buffer: List[TestMetricsUpdate] = []
        self.metric_samples_buffer: List[Dict[str, Any]] = []
        self.dbms_runtime_stats: Dict[str, Dict[str, Any]] = {}
        self.buffer_size = 10
        self._lock = asyncio.Lock()
        self._wall_start: Optional[datetime] = None
        self._start_time_set = False

    def set_wall_start(self, wall_start: datetime) -> None:
        """Зафиксировать wall-clock старт теста для согласованных timestamp realtime-точек."""
        if wall_start.tzinfo is None:
            wall_start = wall_start.replace(tzinfo=timezone.utc)
        self._wall_start = wall_start

    def perf_to_sample_time(self, perf_time: float) -> Tuple[datetime, int]:
        """Преобразовать perf_counter в wall-clock timestamp и elapsed_seconds."""
        elapsed = max(0.0, perf_time - self.start_time)
        wall_start = self._wall_start or datetime.now(timezone.utc)
        sample_ts = wall_start + timedelta(seconds=elapsed)
        return sample_ts, int(elapsed)

    async def drain_realtime_metrics(self) -> None:
        """Сбросить все буферы realtime-метрик перед завершением теста."""
        async with self._lock:
            await self._flush_metric_samples()

    async def _flush_metric_samples(self):
        """Сбросить буфер throughput samples в БД истории"""
        if not self.repository or not self.metric_samples_buffer:
            return

        try:
            await self.repository.add_metric_sample_batch(
                test_run_id=self.test_id,
                samples=self.metric_samples_buffer,
            )
            self.metric_samples_buffer = []
        except Exception as e:
            print(f"[WS] Ошибка сохранения throughput samples: {e}")
    
    def set_progress(self, value: float) -> None:
        """Напрямую установить значение прогресса (0-100)"""
        self._progress = max(0.0, min(100.0, float(value)))

    def set_total_queries(self, total: int):
        """Установить общее количество запросов для расчёта прогресса"""
        self.total_queries = max(1, total)
    
    def set_current_query(self, current: int):
        """Установить текущий обрабатываемый запрос; также обновляет _progress"""
        self.current_query = current
        if self.total_queries > 0:
            self._progress = min(100.0, current / self.total_queries * 100)
    
    def set_duration(self, duration: int):
        """Устаревший метод, оставлен для совместимости"""
        pass

    def get_dbms_runtime_stats(self, db_key: str) -> Dict[str, Any]:
        """Получить агрегаты внутренних метрик, собранные во время realtime-стрима."""
        return self.dbms_runtime_stats.get(db_key, {})

    def ensure_dbms_runtime_stats(self, db_key: str) -> Dict[str, Any]:
        """Инициализировать агрегаты внутренних метрик для подключения."""
        return self.dbms_runtime_stats.setdefault(
            db_key,
            {
                "max_lock_waits": 0,
                "max_deadlocks": 0,
            },
        )

    def _elapsed_seconds(self) -> int:
        """Секунд с момента on_test_start (единый источник для UI-таймера)."""
        if not self._start_time_set:
            return 0
        return max(0, int(time.perf_counter() - self.start_time))
    
    def _calculate_progress(self) -> float:
        """Вернуть текущее значение прогресса"""
        return self._progress
    
    async def on_metrics(
        self,
        db_key: str,
        db_type: str,
        response_time: float,
        attempt_rate: float,
        successful: int,
        failed: int,
        cpu_usage: float = 0,
        memory_usage: float = 0,
        memory_usage_mb: float = 0,
        disk_iops: float = 0,
        network_in: float = 0,
        network_out: float = 0,
        cache_hit_ratio: Optional[float] = None,
        buffer_pool_hit_ratio: Optional[float] = None,
        cache_hit_ratio_status: Optional[str] = None,
        cache_hit_ratio_note: Optional[str] = None,
        cache_hit_ratio_mode: Optional[str] = None,
        lock_waits: int = 0,
        deadlocks: int = 0,
        db_name: str = "",
        sample_timestamp: Optional[datetime] = None,
        elapsed_seconds: Optional[int] = None,
    ):
        """Callback вызываемый при получении новых метрик"""
        async with self._lock:
            if sample_timestamp is not None:
                now = sample_timestamp
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
            else:
                now = datetime.now(timezone.utc)

            if elapsed_seconds is not None:
                elapsed = max(0, int(elapsed_seconds))
            else:
                elapsed = time.perf_counter() - self.start_time
                if elapsed < 0:
                    elapsed = 0
                elapsed = int(elapsed)

            progress = self._calculate_progress()

            await self._publish_metrics(
                db_key=db_key,
                db_type=db_type,
                db_name=db_name,
                now=now,
                elapsed=elapsed,
                progress=progress,
                response_time=response_time,
                attempt_rate=attempt_rate,
                successful=successful,
                failed=failed,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_usage_mb=memory_usage_mb,
                disk_iops=disk_iops,
                network_in=network_in,
                network_out=network_out,
                cache_hit_ratio=cache_hit_ratio,
                buffer_pool_hit_ratio=buffer_pool_hit_ratio,
                cache_hit_ratio_status=cache_hit_ratio_status,
                cache_hit_ratio_note=cache_hit_ratio_note,
                cache_hit_ratio_mode=cache_hit_ratio_mode,
                lock_waits=lock_waits,
                deadlocks=deadlocks,
            )

    async def _publish_metrics(
        self,
        db_key: str,
        db_type: str,
        db_name: str,
        now: datetime,
        elapsed: int,
        progress: float,
        response_time: float,
        attempt_rate: float,
        successful: int,
        failed: int,
        cpu_usage: float,
        memory_usage: float,
        memory_usage_mb: float,
        disk_iops: float,
        network_in: float,
        network_out: float,
        cache_hit_ratio: Optional[float],
        buffer_pool_hit_ratio: Optional[float],
        cache_hit_ratio_status: Optional[str] = None,
        cache_hit_ratio_note: Optional[str] = None,
        cache_hit_ratio_mode: Optional[str] = None,
        lock_waits: int = 0,
        deadlocks: int = 0,
    ) -> None:
        """Отправить метрики в WebSocket и сохранить в историю."""
        update = TestMetricsUpdate(
            test_id=self.test_id,
            db_key=db_key,
            db_type=db_type,
            db_name=db_name or db_type,
            timestamp=now.isoformat(),
            response_time=response_time,
            attempt_rate=attempt_rate,
            active_connections=successful + failed,
            error_count=failed,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            memory_usage_mb=memory_usage_mb,
            disk_iops=disk_iops,
            network_in=network_in,
            network_out=network_out,
            cache_hit_ratio=cache_hit_ratio,
            buffer_pool_hit_ratio=buffer_pool_hit_ratio,
            cache_hit_ratio_status=cache_hit_ratio_status,
            cache_hit_ratio_note=cache_hit_ratio_note,
            cache_hit_ratio_mode=cache_hit_ratio_mode,
            lock_waits=lock_waits,
            deadlocks=deadlocks,
            progress=progress,
            elapsed_seconds=elapsed,
            remaining_seconds=0
        )

        stats = self.ensure_dbms_runtime_stats(db_key)
        stats["max_lock_waits"] = max(int(stats.get("max_lock_waits") or 0), int(lock_waits or 0))
        stats["max_deadlocks"] = max(int(stats.get("max_deadlocks") or 0), int(deadlocks or 0))

        await self.manager.send_metrics_update(update)

        if self.repository:
            try:
                await self.repository.add_time_series_point(
                    test_run_id=self.test_id,
                    db_type=db_type,
                    connection_key=db_key,
                    timestamp=now,
                    response_time=response_time,
                    attempt_rate=attempt_rate,
                    active_connections=successful + failed,
                    error_count=failed,
                    cpu_usage=cpu_usage,
                    memory_usage=memory_usage,
                    memory_usage_mb=memory_usage_mb,
                    disk_iops=disk_iops,
                    network_in=network_in,
                    network_out=network_out,
                )

                self.metric_samples_buffer.append({
                    'db_type': db_type,
                    'connection_key': db_key,
                    'query_id': None,
                    'sample_type': 'throughput_realtime',
                    'timestamp': now,
                    'latency_ms': response_time,
                    'throughput': None,
                    'attempt_rate': attempt_rate,
                    'is_error': failed > 0,
                    'error_message': None,
                })
                if len(self.metric_samples_buffer) >= self.buffer_size:
                    await self._flush_metric_samples()
            except Exception as e:
                print(f"[WS] Ошибка сохранения time_series: {e}")
    
    async def on_status_change(self, status: str, message: str = None):
        """Callback при изменении статуса теста"""
        progress = self._calculate_progress()
        
        if status == "completed":
            progress = 100
        
        update = TestStatusUpdate(
            test_id=self.test_id,
            status=status,
            message=message,
            progress=progress,
            elapsed_seconds=self._elapsed_seconds(),
        )
        
        await self.manager.send_status_update(update)
    
    async def on_test_start(self):
        """Вызывается при начале теста"""
        # Не сбрасываем start_time если она уже установлена (при reconnect)
        if not self._start_time_set:
            self.start_time = time.perf_counter()
            if self._wall_start is None:
                self._wall_start = datetime.now(timezone.utc)
            self._start_time_set = True
        self.current_query = 0
        self._progress = 0.0
        await self.on_status_change("running", "Тестирование начато")
    
    async def on_test_complete(self, summary: Dict[str, Any] = None):
        """Вызывается при завершении теста"""
        self.current_query = self.total_queries
        self._progress = 100.0
        await self.drain_realtime_metrics()
        message = "Тестирование завершено"
        if summary:
            actual_duration = time.perf_counter() - self.start_time
            total_transactions = summary.get('total_transactions')
            message += f". Длительность: {actual_duration:.1f} сек"
            if total_transactions is not None:
                message += f", транзакций: {total_transactions}"
        await self.on_status_change("completed", message)
    
    async def on_backup_status(self, status: str, data: Dict[str, Any] = None):
        """Вызывается при изменении статуса backup/restore/index-операций"""
        await self.manager.send_operation_status(
            self.test_id,
            status,
            data or {},
            elapsed_seconds=self._elapsed_seconds(),
        )

    async def on_test_error(self, error: str):
        """Вызывается при ошибке теста"""
        await self.drain_realtime_metrics()
        await self.on_status_change("failed", f"Ошибка: {error}")
