"""
WebSocket менеджер для real-time обновлений тестирования
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional, Callable
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
    
    # Метрики производительности
    response_time: float = 0.0
    tps: float = 0.0
    throughput: float = 0.0
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
    cache_hit_ratio: float = 0.0
    buffer_pool_hit_ratio: float = 0.0
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
    
    async def send_backup_status(self, test_id: str, status: str, data: Dict[str, Any]):
        """
        Отправить статус backup/restore или index-операции
        
        Args:
            test_id: ID теста
            status: Тип статуса (backup_started, restore_completed, index_creation_started, etc.)
            data: Данные статуса (tables, duration_ms, verified, etc.)
        """
        message = {
            "type": "backup_status",
            "status": status,
            "test_id": test_id,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_test(test_id, message)
        # Также отправляем в глобальный канал
        await self.broadcast_to_test("global", message)

    async def send_operation_status(self, test_id: str, status: str, data: Dict[str, Any]):
        """Совместимый алиас для статусов служебных операций теста"""
        await self.send_backup_status(test_id, status, data)
    
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
        self.total_queries = 1  # Общее количество запросов для теста
        self.current_query = 0  # Текущий обрабатываемый запрос
        self.metrics_buffer: List[TestMetricsUpdate] = []
        self.metric_samples_buffer: List[Dict[str, Any]] = []
        self.buffer_size = 10
        self._lock = asyncio.Lock()

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
    
    def set_total_queries(self, total: int):
        """Установить общее количество запросов для расчёта прогресса"""
        self.total_queries = max(1, total)
    
    def set_current_query(self, current: int):
        """Установить текущий обрабатываемый запрос"""
        self.current_query = current
    
    def set_duration(self, duration: int):
        """Устаревший метод, оставлен для совместимости"""
        pass
    
    def _calculate_progress(self) -> float:
        """Рассчитать прогресс на основе обработанных запросов"""
        return min(100, (self.current_query / self.total_queries) * 100) if self.total_queries > 0 else 0
    
    async def on_metrics(
        self,
        db_key: str,
        db_type: str,
        response_time: float,
        tps: float,
        successful: int,
        failed: int,
        cpu_usage: float = 0,
        memory_usage: float = 0,
        memory_usage_mb: float = 0,
        disk_iops: float = 0,
        network_in: float = 0,
        network_out: float = 0,
        cache_hit_ratio: float = 0,
        buffer_pool_hit_ratio: float = 0,
        lock_waits: int = 0,
        deadlocks: int = 0,
        db_name: str = ""
    ):
        """Callback вызываемый при получении новых метрик"""
        now = datetime.now(timezone.utc)
        elapsed = time.perf_counter() - self.start_time
        if elapsed < 0:
            elapsed = 0
        progress = self._calculate_progress()
        
        update = TestMetricsUpdate(
            test_id=self.test_id,
            db_key=db_key,
            db_type=db_type,
            db_name=db_name or db_type,
            timestamp=now.isoformat(),
            response_time=response_time,
            tps=tps,
            throughput=tps,
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
            lock_waits=lock_waits,
            deadlocks=deadlocks,
            progress=progress,
            elapsed_seconds=int(elapsed),
            remaining_seconds=0
        )
        
        await self.manager.send_metrics_update(update)

        if self.repository:
            try:
                await self.repository.add_time_series_point(
                    test_run_id=self.test_id,
                    db_type=db_type,
                    timestamp=now,
                    response_time=response_time,
                    tps=tps,
                    throughput=tps,
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
                    'throughput': tps,
                    'tps': tps,
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
            progress=progress
        )
        
        await self.manager.send_status_update(update)
    
    async def on_test_start(self):
        """Вызывается при начале теста"""
        # Не сбрасываем start_time если она уже установлена (при reconnect)
        if not hasattr(self, '_start_time_set') or not self._start_time_set:
            self.start_time = time.perf_counter()
            self._start_time_set = True
        self.current_query = 0
        await self.on_status_change("running", "Тестирование начато")
    
    async def on_test_complete(self, summary: Dict[str, Any] = None):
        """Вызывается при завершении теста"""
        self.current_query = self.total_queries
        await self._flush_metric_samples()
        message = "Тестирование завершено"
        if summary:
            actual_duration = time.perf_counter() - self.start_time
            message += f". Длительность: {actual_duration:.1f} сек, TPS: {summary.get('overall_tps', 0):.2f}"
        await self.on_status_change("completed", message)
    
    async def on_backup_status(self, status: str, data: Dict[str, Any] = None):
        """Вызывается при изменении статуса backup/restore/index-операций"""
        await self.manager.send_operation_status(self.test_id, status, data or {})

    async def on_test_error(self, error: str):
        """Вызывается при ошибке теста"""
        await self._flush_metric_samples()
        await self.on_status_change("failed", f"Ошибка: {error}")
