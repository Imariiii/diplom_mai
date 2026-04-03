"""
Async Repository для работы с историей тестов в PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

from backend.database.models import (
    Base, TestRun, TestResult, TimeSeries,
    TestScenario, ScenarioQuery, ScenarioParam
)


def get_local_now():
    """
    Получить текущее время в UTC (timezone-aware).

    Мы сохраняем все метки времени в БД в UTC, чтобы избежать ошибок при
    отображении локального времени и при пересчёте длительности.
    """
    return datetime.now(timezone.utc)


class TestRepository:
    """Репозиторий для работы с тестами"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(bind=self.engine, expire_on_commit=False)
    
    async def init_db(self):
        """Создать все таблицы"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def get_session(self) -> AsyncSession:
        """Получить новую сессию БД"""
        return self.SessionLocal()
    
    # ==================== TestRun CRUD ====================
    
    async def create_test_run(
        self,
        name: str,
        config: Dict[str, Any],
        status: str = 'pending',
        test_run_id: Optional[str] = None
    ) -> TestRun:
        """Создать новый тестовый прогон"""
        async with self.SessionLocal() as session:
            test_run = TestRun(
                id=uuid.UUID(test_run_id) if test_run_id else uuid.uuid4(),
                name=name,
                status=status,
                config=config,
                started_at=get_local_now()
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
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список всех тестовых прогонов"""
        async with self.SessionLocal() as session:
            query = select(TestRun).order_by(desc(TestRun.created_at))
            
            if status:
                query = query.where(TestRun.status == status)
            
            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            test_runs = result.scalars().all()
            return [tr.to_dict() for tr in test_runs]
    
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
        timestamp: datetime,
        response_time: Optional[float] = None,
        tps: Optional[float] = None,
        throughput: Optional[float] = None,
        active_connections: Optional[int] = None,
        error_count: int = 0,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        memory_usage_mb: Optional[float] = None,
        disk_iops: Optional[float] = None,
        network_in: Optional[float] = None,
        network_out: Optional[float] = None
    ) -> TimeSeries:
        """Добавить точку временного ряда"""
        async with self.SessionLocal() as session:
            point = TimeSeries(
                test_run_id=uuid.UUID(test_run_id),
                db_type=db_type,
                timestamp=timestamp,
                response_time=response_time,
                tps=tps,
                throughput=throughput,
                active_connections=active_connections,
                error_count=error_count,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_usage_mb=memory_usage_mb,
                disk_iops=disk_iops,
                network_in=network_in,
                network_out=network_out
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
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Получить временной ряд для теста"""
        async with self.SessionLocal() as session:
            query = select(TimeSeries).where(
                TimeSeries.test_run_id == uuid.UUID(test_run_id)
            ).order_by(TimeSeries.timestamp)
            
            if db_type:
                query = query.where(TimeSeries.db_type == db_type)
            
            query = query.limit(limit)
            result = await session.execute(query)
            points = result.scalars().all()
            return [p.to_dict() for p in points]
    
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
        
        results_1 = {r['db_type']: r for r in run1.get('results', [])}
        results_2 = {r['db_type']: r for r in run2.get('results', [])}
        
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


class ScenarioRepository:
    """Репозиторий для работы со сценариями тестирования"""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(bind=self.engine, expire_on_commit=False)

    async def init_db(self):
        """Создать все таблицы"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """Получить новую сессию БД"""
        return self.SessionLocal()

    # ==================== TestScenario CRUD ====================

    async def create_scenario(
        self,
        name: str,
        description: Optional[str],
        scenario_type: str,
        is_builtin: bool = False
    ) -> TestScenario:
        """Создать новый сценарий"""
        async with self.SessionLocal() as session:
            scenario = TestScenario(
                id=uuid.uuid4(),
                name=name,
                description=description,
                scenario_type=scenario_type,
                is_builtin='t' if is_builtin else 'f',
                is_active='t'
            )
            session.add(scenario)
            await session.commit()
            await session.refresh(scenario)
            return scenario

    async def get_scenario(self, scenario_id: str) -> Optional[TestScenario]:
        """Получить сценарий по ID с запросами и параметрами (eager loading)"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario)
                .options(
                    joinedload(TestScenario.queries).joinedload(ScenarioQuery.params)
                )
                .where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.unique().scalar_one_or_none()
            return scenario

    async def get_scenario_by_name(self, name: str) -> Optional[TestScenario]:
        """Получить сценарий по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.name == name)
            )
            return result.scalar_one_or_none()

    async def get_all_scenarios(
        self,
        limit: int = 100,
        offset: int = 0,
        scenario_type: Optional[str] = None,
        include_builtin: bool = True
    ) -> List[Dict[str, Any]]:
        """Получить список всех сценариев"""
        async with self.SessionLocal() as session:
            query = select(TestScenario).options(
                joinedload(TestScenario.queries).joinedload(ScenarioQuery.params)
            )

            if scenario_type:
                query = query.where(TestScenario.scenario_type == scenario_type)

            if not include_builtin:
                query = query.where(TestScenario.is_builtin == 'f')

            query = query.order_by(desc(TestScenario.created_at)).offset(offset).limit(limit)
            result = await session.execute(query)
            scenarios = result.unique().scalars().all()
            return [s.to_dict() for s in scenarios]

    async def update_scenario(
        self,
        scenario_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scenario_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[TestScenario]:
        """Обновить сценарий"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.scalar_one_or_none()

            if scenario:
                if name is not None:
                    scenario.name = name
                if description is not None:
                    scenario.description = description
                if scenario_type is not None:
                    scenario.scenario_type = scenario_type
                if is_active is not None:
                    scenario.is_active = 't' if is_active else 'f'

                await session.commit()
                await session.refresh(scenario)

            return scenario

    async def delete_scenario(self, scenario_id: str) -> bool:
        """Удалить сценарий (только если не built-in)"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.scalar_one_or_none()

            if scenario and scenario.is_builtin == 'f':
                await session.delete(scenario)
                await session.commit()
                return True
            return False

    async def clone_scenario(self, scenario_id: str, new_name: str) -> Optional[TestScenario]:
        """Клонировать сценарий"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.id == uuid.UUID(scenario_id))
            )
            original = result.scalar_one_or_none()

            if not original:
                return None

            cloned = TestScenario(
                id=uuid.uuid4(),
                name=new_name,
                description=f"Копия: {original.description}" if original.description else None,
                scenario_type=original.scenario_type,
                is_builtin='f',
                is_active='t'
            )
            session.add(cloned)
            await session.flush()

            for orig_query in original.queries:
                new_query = ScenarioQuery(
                    id=uuid.uuid4(),
                    scenario_id=cloned.id,
                    sql_template=orig_query.sql_template,
                    query_type=orig_query.query_type,
                    weight=orig_query.weight,
                    order_index=orig_query.order_index,
                    description=orig_query.description
                )
                session.add(new_query)
                await session.flush()

                for orig_param in orig_query.params:
                    new_param = ScenarioParam(
                        id=uuid.uuid4(),
                        query_id=new_query.id,
                        param_name=orig_param.param_name,
                        param_type=orig_param.param_type,
                        min_value=orig_param.min_value,
                        max_value=orig_param.max_value,
                        string_pattern=orig_param.string_pattern,
                        string_length=orig_param.string_length,
                        table_ref=orig_param.table_ref,
                        column_ref=orig_param.column_ref,
                        current_value=orig_param.current_value,
                        step=orig_param.step
                    )
                    session.add(new_param)

            await session.commit()
            await session.refresh(cloned)
            return cloned

    # ==================== ScenarioQuery CRUD ====================

    async def add_query_to_scenario(
        self,
        scenario_id: str,
        sql_template: str,
        query_type: str,
        weight: int = 1,
        order_index: int = 0,
        description: Optional[str] = None
    ) -> ScenarioQuery:
        """Добавить запрос в сценарий"""
        async with self.SessionLocal() as session:
            query = ScenarioQuery(
                id=uuid.uuid4(),
                scenario_id=uuid.UUID(scenario_id),
                sql_template=sql_template,
                query_type=query_type,
                weight=weight,
                order_index=order_index,
                description=description
            )
            session.add(query)
            await session.commit()
            await session.refresh(query)
            return query

    async def get_query(self, query_id: str) -> Optional[ScenarioQuery]:
        """Получить запрос по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            return result.scalar_one_or_none()

    async def update_query(
        self,
        query_id: str,
        sql_template: Optional[str] = None,
        query_type: Optional[str] = None,
        weight: Optional[int] = None,
        order_index: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[ScenarioQuery]:
        """Обновить запрос"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            query = result.scalar_one_or_none()

            if query:
                if sql_template is not None:
                    query.sql_template = sql_template
                if query_type is not None:
                    query.query_type = query_type
                if weight is not None:
                    query.weight = weight
                if order_index is not None:
                    query.order_index = order_index
                if description is not None:
                    query.description = description

                await session.commit()
                await session.refresh(query)

            return query

    async def delete_query(self, query_id: str) -> bool:
        """Удалить запрос из сценария"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            query = result.scalar_one_or_none()

            if query:
                await session.delete(query)
                await session.commit()
                return True
            return False

    # ==================== ScenarioParam CRUD ====================

    async def add_param_to_query(
        self,
        query_id: str,
        param_name: str,
        param_type: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        string_pattern: Optional[str] = None,
        string_length: Optional[int] = None,
        table_ref: Optional[str] = None,
        column_ref: Optional[str] = None,
        current_value: int = 0,
        step: int = 1
    ) -> ScenarioParam:
        """Добавить параметр к запросу"""
        async with self.SessionLocal() as session:
            param = ScenarioParam(
                id=uuid.uuid4(),
                query_id=uuid.UUID(query_id),
                param_name=param_name,
                param_type=param_type,
                min_value=min_value,
                max_value=max_value,
                string_pattern=string_pattern,
                string_length=string_length,
                table_ref=table_ref,
                column_ref=column_ref,
                current_value=current_value,
                step=step
            )
            session.add(param)
            await session.commit()
            await session.refresh(param)
            return param

    async def get_param(self, param_id: str) -> Optional[ScenarioParam]:
        """Получить параметр по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            return result.scalar_one_or_none()

    async def update_param(
        self,
        param_id: str,
        param_name: Optional[str] = None,
        param_type: Optional[str] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        string_pattern: Optional[str] = None,
        string_length: Optional[int] = None,
        table_ref: Optional[str] = None,
        column_ref: Optional[str] = None,
        current_value: Optional[int] = None,
        step: Optional[int] = None
    ) -> Optional[ScenarioParam]:
        """Обновить параметр"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param:
                if param_name is not None:
                    param.param_name = param_name
                if param_type is not None:
                    param.param_type = param_type
                if min_value is not None:
                    param.min_value = min_value
                if max_value is not None:
                    param.max_value = max_value
                if string_pattern is not None:
                    param.string_pattern = string_pattern
                if string_length is not None:
                    param.string_length = string_length
                if table_ref is not None:
                    param.table_ref = table_ref
                if column_ref is not None:
                    param.column_ref = column_ref
                if current_value is not None:
                    param.current_value = current_value
                if step is not None:
                    param.step = step

                await session.commit()
                await session.refresh(param)

            return param

    async def delete_param(self, param_id: str) -> bool:
        """Удалить параметр"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param:
                await session.delete(param)
                await session.commit()
                return True
            return False

    async def increment_sequential_param(self, param_id: str) -> int:
        """Инкрементировать значение sequential параметра"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param and param.param_type == 'sequential_int':
                old_value = param.current_value
                param.current_value += param.step
                await session.commit()
                return old_value
            return 0

    # ==================== Helper Methods ====================

    async def get_scenario_for_execution(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Получить сценарий в формате для выполнения теста"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario)
                .options(joinedload(TestScenario.queries).joinedload(ScenarioQuery.params))
                .where(
                    TestScenario.id == uuid.UUID(scenario_id),
                    TestScenario.is_active == 't'
                )
            )
            scenario = result.unique().scalar_one_or_none()

            if not scenario:
                return None

            return {
                'id': str(scenario.id),
                'name': scenario.name,
                'scenario_type': scenario.scenario_type,
                'queries': [
                    {
                        'id': str(q.id),
                        'sql_template': q.sql_template,
                        'query_type': q.query_type,
                        'weight': q.weight,
                        'params': [
                            {
                                'param_name': p.param_name,
                                'param_type': p.param_type,
                                'min_value': p.min_value,
                                'max_value': p.max_value,
                                'table_ref': p.table_ref,
                                'column_ref': p.column_ref,
                            }
                            for p in q.params
                        ]
                    }
                    for q in scenario.queries
                ]
            }
