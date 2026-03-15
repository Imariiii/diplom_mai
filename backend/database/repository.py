"""
Repository для работы с историей тестов в PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session, joinedload

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
        self.engine = create_engine(database_url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
    
    def get_session(self) -> Session:
        """Получить новую сессию БД"""
        return self.SessionLocal()
    
    # ==================== TestRun CRUD ====================
    
    def create_test_run(
        self,
        name: str,
        config: Dict[str, Any],
        status: str = 'pending',
        test_run_id: Optional[str] = None
    ) -> TestRun:
        """Создать новый тестовый прогон"""
        with self.get_session() as session:
            test_run = TestRun(
                id=uuid.UUID(test_run_id) if test_run_id else uuid.uuid4(),
                name=name,
                status=status,
                config=config,
                started_at=get_local_now()
            )
            session.add(test_run)
            session.commit()
            session.refresh(test_run)
            return test_run
    
    def get_test_run(self, test_run_id: str) -> Optional[TestRun]:
        """Получить тестовый прогон по ID"""
        with self.get_session() as session:
            return session.query(TestRun).filter(
                TestRun.id == uuid.UUID(test_run_id)
            ).first()
    
    def get_test_run_with_results(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        """Получить тестовый прогон с результатами"""
        with self.get_session() as session:
            test_run = session.query(TestRun).filter(
                TestRun.id == uuid.UUID(test_run_id)
            ).first()
            
            if not test_run:
                return None
            
            result = test_run.to_dict()
            result['results'] = [r.to_dict() for r in test_run.results]
            return result
    
    def get_all_test_runs(
        self, 
        limit: int = 50, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список всех тестовых прогонов"""
        with self.get_session() as session:
            query = session.query(TestRun).order_by(desc(TestRun.created_at))
            
            if status:
                query = query.filter(TestRun.status == status)
            
            test_runs = query.offset(offset).limit(limit).all()
            return [tr.to_dict() for tr in test_runs]
    
    def update_test_run_status(
        self, 
        test_run_id: str, 
        status: str,
        summary: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
    ) -> Optional[TestRun]:
        """Обновить статус тестового прогона"""
        with self.get_session() as session:
            test_run = session.query(TestRun).filter(
                TestRun.id == uuid.UUID(test_run_id)
            ).first()
            
            if test_run:
                test_run.status = status

                # Обновляем время начала/окончания, если передано
                if started_at is not None:
                    test_run.started_at = started_at
                if finished_at is not None:
                    test_run.finished_at = finished_at
                elif status in ['completed', 'failed']:
                    # По‑умолчанию ставим момент обновления, если не задано явно
                    test_run.finished_at = get_local_now()

                if summary:
                    test_run.summary = summary
                session.commit()
                session.refresh(test_run)
            
            return test_run
    
    def delete_test_run(self, test_run_id: str) -> bool:
        """Удалить тестовый прогон"""
        with self.get_session() as session:
            test_run = session.query(TestRun).filter(
                TestRun.id == uuid.UUID(test_run_id)
            ).first()
            
            if test_run:
                session.delete(test_run)
                session.commit()
                return True
            return False
    
    # ==================== TestResult CRUD ====================
    
    def add_test_result(
        self,
        test_run_id: str,
        db_type: str,
        metrics: Dict[str, Any],
        query_id: Optional[str] = None,
        system_metrics: Optional[Dict[str, Any]] = None,
        dbms_metrics: Optional[Dict[str, Any]] = None
    ) -> TestResult:
        """Добавить результат теста для СУБД"""
        with self.get_session() as session:
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
            session.commit()
            session.refresh(result)
            return result
    
    def get_test_results(self, test_run_id: str) -> List[Dict[str, Any]]:
        """Получить все результаты для тестового прогона"""
        with self.get_session() as session:
            results = session.query(TestResult).filter(
                TestResult.test_run_id == uuid.UUID(test_run_id)
            ).all()
            return [r.to_dict() for r in results]
    
    # ==================== TimeSeries CRUD ====================
    
    def add_time_series_point(
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
        with self.get_session() as session:
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
            session.commit()
            session.refresh(point)
            return point
    
    def add_time_series_batch(
        self,
        test_run_id: str,
        points: List[Dict[str, Any]]
    ) -> int:
        """Добавить несколько точек временного ряда"""
        with self.get_session() as session:
            for point_data in points:
                point = TimeSeries(
                    test_run_id=uuid.UUID(test_run_id),
                    **point_data
                )
                session.add(point)
            session.commit()
            return len(points)
    
    def get_time_series(
        self, 
        test_run_id: str, 
        db_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Получить временной ряд для теста"""
        with self.get_session() as session:
            query = session.query(TimeSeries).filter(
                TimeSeries.test_run_id == uuid.UUID(test_run_id)
            ).order_by(TimeSeries.timestamp)
            
            if db_type:
                query = query.filter(TimeSeries.db_type == db_type)
            
            points = query.limit(limit).all()
            return [p.to_dict() for p in points]
    
    # ==================== Comparison ====================
    
    def compare_test_runs(
        self, 
        test_run_id_1: str, 
        test_run_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """Сравнить два тестовых прогона"""
        run1 = self.get_test_run_with_results(test_run_id_1)
        run2 = self.get_test_run_with_results(test_run_id_2)
        
        if not run1 or not run2:
            return None
        
        comparison = {
            'test_1': run1,
            'test_2': run2,
            'delta': {}
        }
        
        # Вычисляем дельту по каждой СУБД
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
                    # Положительная дельта = улучшение для TPS, ухудшение для времени
                    delta[metric] = {
                        'test_1': v1,
                        'test_2': v2,
                        'diff': v2 - v1,
                        'diff_percent': ((v2 - v1) / v1 * 100) if v1 != 0 else 0
                    }
            
            comparison['delta'][db_type] = delta
        
        return comparison
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить общую статистику по тестам"""
        with self.get_session() as session:
            total_runs = session.query(TestRun).count()
            completed_runs = session.query(TestRun).filter(TestRun.status == 'completed').count()
            failed_runs = session.query(TestRun).filter(TestRun.status == 'failed').count()

            return {
                'total_runs': total_runs,
                'completed_runs': completed_runs,
                'failed_runs': failed_runs,
                'success_rate': (completed_runs / total_runs * 100) if total_runs > 0 else 0
            }


class ScenarioRepository:
    """Репозиторий для работы со сценариями тестирования"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def get_session(self) -> Session:
        """Получить новую сессию БД"""
        return self.SessionLocal()

    # ==================== TestScenario CRUD ====================

    def create_scenario(
        self,
        name: str,
        description: Optional[str],
        scenario_type: str,
        is_builtin: bool = False
    ) -> TestScenario:
        """Создать новый сценарий"""
        with self.get_session() as session:
            scenario = TestScenario(
                id=uuid.uuid4(),
                name=name,
                description=description,
                scenario_type=scenario_type,
                is_builtin='t' if is_builtin else 'f',
                is_active='t'
            )
            session.add(scenario)
            session.commit()
            session.refresh(scenario)
            return scenario

    def get_scenario(self, scenario_id: str) -> Optional[TestScenario]:
        """Получить сценарий по ID с запросами и параметрами (eager loading)"""
        with self.get_session() as session:
            scenario = session.query(TestScenario).options(
                joinedload(TestScenario.queries).joinedload(ScenarioQuery.params)
            ).filter(
                TestScenario.id == uuid.UUID(scenario_id)
            ).first()
            # Явно загружаем связанные данные до закрытия сессии
            if scenario:
                for query in scenario.queries:
                    _ = query.params  # Touch to load
            return scenario

    def get_scenario_by_name(self, name: str) -> Optional[TestScenario]:
        """Получить сценарий по имени"""
        with self.get_session() as session:
            return session.query(TestScenario).filter(
                TestScenario.name == name
            ).first()

    def get_all_scenarios(
        self,
        limit: int = 100,
        offset: int = 0,
        scenario_type: Optional[str] = None,
        include_builtin: bool = True
    ) -> List[Dict[str, Any]]:
        """Получить список всех сценариев"""
        with self.get_session() as session:
            query = session.query(TestScenario)

            if scenario_type:
                query = query.filter(TestScenario.scenario_type == scenario_type)

            if not include_builtin:
                query = query.filter(TestScenario.is_builtin == 'f')

            scenarios = query.order_by(desc(TestScenario.created_at)).offset(offset).limit(limit).all()
            return [s.to_dict() for s in scenarios]

    def update_scenario(
        self,
        scenario_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scenario_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[TestScenario]:
        """Обновить сценарий"""
        with self.get_session() as session:
            scenario = session.query(TestScenario).filter(
                TestScenario.id == uuid.UUID(scenario_id)
            ).first()

            if scenario:
                if name is not None:
                    scenario.name = name
                if description is not None:
                    scenario.description = description
                if scenario_type is not None:
                    scenario.scenario_type = scenario_type
                if is_active is not None:
                    scenario.is_active = 't' if is_active else 'f'

                session.commit()
                session.refresh(scenario)

            return scenario

    def delete_scenario(self, scenario_id: str) -> bool:
        """Удалить сценарий (только если не built-in)"""
        with self.get_session() as session:
            scenario = session.query(TestScenario).filter(
                TestScenario.id == uuid.UUID(scenario_id)
            ).first()

            if scenario and scenario.is_builtin == 'f':
                session.delete(scenario)
                session.commit()
                return True
            return False

    def clone_scenario(self, scenario_id: str, new_name: str) -> Optional[TestScenario]:
        """Клонировать сценарий"""
        with self.get_session() as session:
            original = session.query(TestScenario).filter(
                TestScenario.id == uuid.UUID(scenario_id)
            ).first()

            if not original:
                return None

            # Создаём новый сценарий
            cloned = TestScenario(
                id=uuid.uuid4(),
                name=new_name,
                description=f"Копия: {original.description}" if original.description else None,
                scenario_type=original.scenario_type,
                is_builtin='f',
                is_active='t'
            )
            session.add(cloned)
            session.flush()

            # Копируем запросы
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
                session.flush()

                # Копируем параметры
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

            session.commit()
            session.refresh(cloned)
            return cloned

    # ==================== ScenarioQuery CRUD ====================

    def add_query_to_scenario(
        self,
        scenario_id: str,
        sql_template: str,
        query_type: str,
        weight: int = 1,
        order_index: int = 0,
        description: Optional[str] = None
    ) -> ScenarioQuery:
        """Добавить запрос в сценарий"""
        with self.get_session() as session:
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
            session.commit()
            session.refresh(query)
            return query

    def get_query(self, query_id: str) -> Optional[ScenarioQuery]:
        """Получить запрос по ID"""
        with self.get_session() as session:
            return session.query(ScenarioQuery).filter(
                ScenarioQuery.id == uuid.UUID(query_id)
            ).first()

    def update_query(
        self,
        query_id: str,
        sql_template: Optional[str] = None,
        query_type: Optional[str] = None,
        weight: Optional[int] = None,
        order_index: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[ScenarioQuery]:
        """Обновить запрос"""
        with self.get_session() as session:
            query = session.query(ScenarioQuery).filter(
                ScenarioQuery.id == uuid.UUID(query_id)
            ).first()

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

                session.commit()
                session.refresh(query)

            return query

    def delete_query(self, query_id: str) -> bool:
        """Удалить запрос из сценария"""
        with self.get_session() as session:
            query = session.query(ScenarioQuery).filter(
                ScenarioQuery.id == uuid.UUID(query_id)
            ).first()

            if query:
                session.delete(query)
                session.commit()
                return True
            return False

    # ==================== ScenarioParam CRUD ====================

    def add_param_to_query(
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
        with self.get_session() as session:
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
            session.commit()
            session.refresh(param)
            return param

    def get_param(self, param_id: str) -> Optional[ScenarioParam]:
        """Получить параметр по ID"""
        with self.get_session() as session:
            return session.query(ScenarioParam).filter(
                ScenarioParam.id == uuid.UUID(param_id)
            ).first()

    def update_param(
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
        with self.get_session() as session:
            param = session.query(ScenarioParam).filter(
                ScenarioParam.id == uuid.UUID(param_id)
            ).first()

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

                session.commit()
                session.refresh(param)

            return param

    def delete_param(self, param_id: str) -> bool:
        """Удалить параметр"""
        with self.get_session() as session:
            param = session.query(ScenarioParam).filter(
                ScenarioParam.id == uuid.UUID(param_id)
            ).first()

            if param:
                session.delete(param)
                session.commit()
                return True
            return False

    def increment_sequential_param(self, param_id: str) -> int:
        """Инкрементировать значение sequential параметра"""
        with self.get_session() as session:
            param = session.query(ScenarioParam).filter(
                ScenarioParam.id == uuid.UUID(param_id)
            ).first()

            if param and param.param_type == 'sequential_int':
                old_value = param.current_value
                param.current_value += param.step
                session.commit()
                return old_value
            return 0

    # ==================== Helper Methods ====================

    def get_scenario_for_execution(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Получить сценарий в формате для выполнения теста"""
        with self.get_session() as session:
            scenario = session.query(TestScenario).filter(
                TestScenario.id == uuid.UUID(scenario_id),
                TestScenario.is_active == 't'
            ).first()

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
