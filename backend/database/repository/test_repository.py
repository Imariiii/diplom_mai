"""
TestRepository для работы с историей тестов в PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

from backend.database.models import Base, MetricSample, TestRun, TestResult, TimeSeries
from backend.database.repository.base import BaseRepository, get_local_now


class TestRepository(BaseRepository):
    """Репозиторий для работы с тестами"""

    def _result_group_key(self, result: Dict[str, Any]) -> str:
        """Получить устойчивый ключ результата для сравнений"""
        metrics = result.get('metrics', {}) or {}
        return (
            metrics.get('connection_key')
            or metrics.get('db_name')
            or result.get('db_type')
            or 'unknown'
        )

    async def init_db(self):
        """Создать все таблицы"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ==================== TestRun CRUD ====================

    async def create_test_run(
        self,
        name: str,
        config: Dict[str, Any],
        status: str = 'pending',
        test_run_id: Optional[str] = None,
        database_group_id: Optional[str] = None,
    ) -> TestRun:
        """Создать новый тестовый прогон"""
        import uuid as _uuid
        logical_db_uuid = None
        if database_group_id:
            try:
                logical_db_uuid = _uuid.UUID(database_group_id)
            except (ValueError, AttributeError):
                pass

        async with self.SessionLocal() as session:
            test_run = TestRun(
                id=uuid.UUID(test_run_id) if test_run_id else uuid.uuid4(),
                name=name,
                status=status,
                config=config,
                started_at=get_local_now(),
                database_group_id=logical_db_uuid,
            )
            session.add(test_run)
            await session.commit()
            await session.refresh(test_run)
            return test_run

    async def get_test_run(self, test_run_id: str) -> Optional[TestRun]:
        """Получить тестовый прогон по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestRun).where(TestRun.id == uuid.UUID(test_run_id))
            )
            return result.scalar_one_or_none()

    async def get_test_run_with_results(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        """Получить тестовый прогон с результатами"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestRun)
                .options(joinedload(TestRun.results))
                .where(TestRun.id == uuid.UUID(test_run_id))
            )
            test_run = result.unique().scalar_one_or_none()

            if not test_run:
                return None

            result_dict = test_run.to_dict()
            result_dict['results'] = [r.to_dict() for r in test_run.results]
            return result_dict

    async def get_all_test_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        database_group_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получить список всех тестовых прогонов"""
        import uuid as _uuid
        async with self.SessionLocal() as session:
            query = select(TestRun).order_by(desc(TestRun.created_at))

            if status:
                query = query.where(TestRun.status == status)

            if database_group_id:
                try:
                    logical_db_uuid = _uuid.UUID(database_group_id)
                    query = query.where(TestRun.database_group_id == logical_db_uuid)
                except (ValueError, AttributeError):
                    pass

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            test_runs = result.scalars().all()
            return [tr.to_dict() for tr in test_runs]

    async def count_test_runs(
        self,
        status: Optional[str] = None,
        database_group_id: Optional[str] = None,
    ) -> int:
        """Получить общее количество тестовых прогонов с учётом фильтров."""
        import uuid as _uuid

        async with self.SessionLocal() as session:
            query = select(func.count()).select_from(TestRun)

            if status:
                query = query.where(TestRun.status == status)

            if database_group_id:
                try:
                    logical_db_uuid = _uuid.UUID(database_group_id)
                    query = query.where(TestRun.database_group_id == logical_db_uuid)
                except (ValueError, AttributeError):
                    pass

            result = await session.execute(query)
            return int(result.scalar() or 0)

    async def update_test_run_status(
        self,
        test_run_id: str,
        status: str,
        summary: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
    ) -> Optional[TestRun]:
        """Обновить статус тестового прогона"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestRun).where(TestRun.id == uuid.UUID(test_run_id))
            )
            test_run = result.scalar_one_or_none()

            if test_run:
                test_run.status = status

                if started_at is not None:
                    test_run.started_at = started_at
                if finished_at is not None:
                    test_run.finished_at = finished_at
                elif status in ['completed', 'failed']:
                    test_run.finished_at = get_local_now()

                if summary:
                    test_run.summary = summary
                await session.commit()
                await session.refresh(test_run)

            return test_run

    async def update_test_run_config(
        self,
        test_run_id: str,
        config: Dict[str, Any],
    ) -> Optional[TestRun]:
        """Обновить config тестового прогона."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestRun).where(TestRun.id == uuid.UUID(test_run_id))
            )
            test_run = result.scalar_one_or_none()
            if test_run:
                test_run.config = config
                await session.commit()
                await session.refresh(test_run)
            return test_run

    async def delete_test_run(self, test_run_id: str) -> bool:
        """Удалить тестовый прогон"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestRun).where(TestRun.id == uuid.UUID(test_run_id))
            )
            test_run = result.scalar_one_or_none()

            if test_run:
                await session.delete(test_run)
                await session.commit()
                return True
            return False

    # ==================== TestResult CRUD ====================

    async def add_test_result(
        self,
        test_run_id: str,
        db_type: str,
        metrics: Dict[str, Any],
        query_id: Optional[str] = None,
        system_metrics: Optional[Dict[str, Any]] = None,
        dbms_metrics: Optional[Dict[str, Any]] = None
    ) -> TestResult:
        """Добавить результат теста для СУБД"""
        async with self.SessionLocal() as session:
            result = TestResult(
                id=uuid.uuid4(),
                test_run_id=uuid.UUID(test_run_id),
                db_type=db_type,
                query_id=query_id,
                metrics=metrics,
                system_metrics=system_metrics,
                dbms_metrics=dbms_metrics
            )
            session.add(result)
            await session.commit()
            await session.refresh(result)
            return result

    async def get_test_results(self, test_run_id: str) -> List[Dict[str, Any]]:
        """Получить все результаты для тестового прогона"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestResult).where(TestResult.test_run_id == uuid.UUID(test_run_id))
            )
            results = result.scalars().all()
            return [r.to_dict() for r in results]

    # ==================== TimeSeries CRUD ====================

    async def add_time_series_point(
        self,
        test_run_id: str,
        db_type: str,
        connection_key: Optional[str],
        timestamp: datetime,
        response_time: Optional[float] = None,
        attempt_rate: Optional[float] = None,
        throughput: Optional[float] = None,
        successful_throughput: Optional[float] = None,
        active_connections: Optional[int] = None,
        error_count: int = 0,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        memory_usage_mb: Optional[float] = None,
        disk_iops: Optional[float] = None,
        disk_ops_per_sec: Optional[float] = None,
        network_in: Optional[float] = None,
        network_out: Optional[float] = None,
        network_in_mib_per_sec: Optional[float] = None,
        network_out_mib_per_sec: Optional[float] = None,
    ) -> TimeSeries:
        """
        Добавить точку временного ряда.

        Legacy: колонка throughput = attempt_rate (все запросы/с).
        Колонка tps = successful_throughput (успешных/с), если передана.
        disk_iops: rate (disk_ops_per_sec), если передан, иначе cumulative legacy.
        network_in/out: rate MiB/s, если переданы *_mib_per_sec, иначе cumulative legacy.
        """
        async with self.SessionLocal() as session:
            stored_attempt_rate = attempt_rate if attempt_rate is not None else throughput
            stored_tps = successful_throughput if successful_throughput is not None else None
            stored_disk = (
                disk_ops_per_sec if disk_ops_per_sec is not None else disk_iops
            )
            stored_net_in = (
                network_in_mib_per_sec
                if network_in_mib_per_sec is not None
                else network_in
            )
            stored_net_out = (
                network_out_mib_per_sec
                if network_out_mib_per_sec is not None
                else network_out
            )
            point = TimeSeries(
                test_run_id=uuid.UUID(test_run_id),
                db_type=db_type,
                connection_key=connection_key,
                timestamp=timestamp,
                response_time=response_time,
                tps=stored_tps,
                throughput=stored_attempt_rate,
                active_connections=active_connections,
                error_count=error_count,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_usage_mb=memory_usage_mb,
                disk_iops=stored_disk,
                network_in=stored_net_in,
                network_out=stored_net_out,
            )
            session.add(point)
            await session.commit()
            await session.refresh(point)
            return point

    async def add_time_series_batch(
        self,
        test_run_id: str,
        points: List[Dict[str, Any]]
    ) -> int:
        """Добавить несколько точек временного ряда"""
        async with self.SessionLocal() as session:
            for point_data in points:
                point = TimeSeries(
                    test_run_id=uuid.UUID(test_run_id),
                    **point_data
                )
                session.add(point)
            await session.commit()
            return len(points)

    async def get_time_series(
        self,
        test_run_id: str,
        db_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить временной ряд для теста"""
        async with self.SessionLocal() as session:
            base_conditions = [TimeSeries.test_run_id == uuid.UUID(test_run_id)]

            if db_type:
                base_conditions.append(TimeSeries.db_type == db_type)

            query = (
                select(TimeSeries)
                .where(*base_conditions)
                .order_by(
                    TimeSeries.connection_key,
                    TimeSeries.db_type,
                    TimeSeries.timestamp,
                )
            )

            if limit is not None and limit > 0:
                # Ограничение применяется на каждую серию connection_key|db_type,
                # чтобы поздние СУБД не терялись при последовательных прогонах.
                result = await session.execute(query)
                points = result.scalars().all()
                by_series: Dict[str, List[TimeSeries]] = {}
                for point in points:
                    series_key = point.connection_key or point.db_type
                    if series_key not in by_series:
                        by_series[series_key] = []
                    by_series[series_key].append(point)

                limited: List[TimeSeries] = []
                for series_key in sorted(by_series.keys()):
                    limited.extend(by_series[series_key][:limit])
                limited.sort(key=lambda p: p.timestamp)
                return [p.to_dict() for p in limited]

            result = await session.execute(query)
            points = result.scalars().all()
            return [p.to_dict() for p in points]

    # ==================== MetricSample CRUD ====================

    async def add_metric_sample_batch(
        self,
        test_run_id: str,
        samples: List[Dict[str, Any]]
    ) -> int:
        """Добавить несколько raw/semiraw sample-метрик"""
        if not samples:
            return 0

        async with self.SessionLocal() as session:
            for sample_data in samples:
                sample = MetricSample(
                    test_run_id=uuid.UUID(test_run_id),
                    db_type=sample_data.get('db_type'),
                    connection_key=sample_data.get('connection_key'),
                    query_id=sample_data.get('query_id'),
                    sample_type=sample_data.get('sample_type', 'request_latency'),
                    timestamp=sample_data.get('timestamp'),
                    latency_ms=sample_data.get('latency_ms'),
                    throughput=sample_data.get('throughput'),
                    tps=sample_data.get('attempt_rate', sample_data.get('tps')),
                    is_error='t' if sample_data.get('is_error') else 'f',
                    error_message=sample_data.get('error_message'),
                )
                session.add(sample)

            await session.commit()
            return len(samples)

    async def get_metric_samples(
        self,
        test_run_id: str,
        db_type: Optional[str] = None,
        sample_type: Optional[str] = None,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """Получить raw/semiraw sample-метрики теста"""
        async with self.SessionLocal() as session:
            query = select(MetricSample).where(
                MetricSample.test_run_id == uuid.UUID(test_run_id)
            ).order_by(MetricSample.timestamp)

            if db_type:
                query = query.where(MetricSample.db_type == db_type)
            if sample_type:
                query = query.where(MetricSample.sample_type == sample_type)

            query = query.limit(limit)
            result = await session.execute(query)
            samples = result.scalars().all()
            return [sample.to_dict() for sample in samples]

    async def get_test_metrics_raw(
        self,
        test_run_id: str,
        db_type: Optional[str] = None,
        sample_type: Optional[str] = None,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """Получить raw метрики теста для сравнительного анализа"""
        return await self.get_metric_samples(
            test_run_id,
            db_type=db_type,
            sample_type=sample_type,
            limit=limit,
        )

    async def get_test_error_report(
        self,
        test_run_id: str,
        db_type: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Получить сгруппированный отчёт по ошибкам raw-запросов теста."""
        async with self.SessionLocal() as session:
            query = (
                select(MetricSample)
                .where(
                    MetricSample.test_run_id == uuid.UUID(test_run_id),
                    MetricSample.is_error == 't',
                    MetricSample.sample_type == 'request_latency',
                )
                .order_by(MetricSample.timestamp)
            )

            if db_type:
                query = query.where(MetricSample.db_type == db_type)

            result = await session.execute(query)
            errors = [sample.to_dict() for sample in result.scalars().all()]

        groups: Dict[str, Dict[str, Any]] = {}
        for sample in errors:
            group_key = self._error_group_key(sample.get('error_message'))
            group = groups.setdefault(
                group_key,
                {
                    'message': group_key,
                    'count': 0,
                    'db_type': sample.get('db_type'),
                    'query_id': sample.get('query_id'),
                    'first_seen': sample.get('timestamp'),
                    'last_seen': sample.get('timestamp'),
                    'example': sample.get('error_message'),
                },
            )
            group['count'] += 1
            group['last_seen'] = sample.get('timestamp')

        return {
            'test_run_id': test_run_id,
            'total_errors': len(errors),
            'groups': sorted(groups.values(), key=lambda item: item['count'], reverse=True),
            'samples': errors[:limit],
        }

    def _error_group_key(self, error_message: Optional[str]) -> str:
        """Нормализовать текст ошибки для группировки похожих исключений."""
        if not error_message:
            return "Ошибка без сообщения"
        first_line = error_message.splitlines()[0].strip()
        return first_line or "Ошибка без сообщения"

    # ==================== Comparison ====================

    async def compare_test_runs(
        self,
        test_run_id_1: str,
        test_run_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """Сравнить два тестовых прогона"""
        run1 = await self.get_test_run_with_results(test_run_id_1)
        run2 = await self.get_test_run_with_results(test_run_id_2)

        if not run1 or not run2:
            return None

        comparison = {
            'test_1': run1,
            'test_2': run2,
            'delta': {}
        }

        results_1 = {self._result_group_key(r): r for r in run1.get('results', [])}
        results_2 = {self._result_group_key(r): r for r in run2.get('results', [])}

        for db_type in set(results_1.keys()) | set(results_2.keys()):
            r1 = results_1.get(db_type, {}).get('metrics', {})
            r2 = results_2.get(db_type, {}).get('metrics', {})

            delta = {}
            for metric in ['avg_time_ms', 'p50_time_ms', 'p95_time_ms', 'p99_time_ms', 'tps']:
                v1 = r1.get(metric, 0)
                v2 = r2.get(metric, 0)
                if v1 and v2:
                    delta[metric] = {
                        'test_1': v1,
                        'test_2': v2,
                        'diff': v2 - v1,
                        'diff_percent': ((v2 - v1) / v1 * 100) if v1 != 0 else 0
                    }

            comparison['delta'][db_type] = delta

        return comparison

    async def get_statistics(self) -> Dict[str, Any]:
        """Получить общую статистику по тестам"""
        async with self.SessionLocal() as session:
            total_result = await session.execute(select(func.count()).select_from(TestRun))
            total_runs = total_result.scalar()

            completed_result = await session.execute(
                select(func.count()).select_from(TestRun).where(TestRun.status == 'completed')
            )
            completed_runs = completed_result.scalar()

            failed_result = await session.execute(
                select(func.count()).select_from(TestRun).where(TestRun.status == 'failed')
            )
            failed_runs = failed_result.scalar()

            return {
                'total_runs': total_runs,
                'completed_runs': completed_runs,
                'failed_runs': failed_runs,
                'success_rate': (completed_runs / total_runs * 100) if total_runs > 0 else 0
            }
