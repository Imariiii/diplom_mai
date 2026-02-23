"""
Repository для работы с историей тестов в PostgreSQL
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database.models import Base, TestRun, TestResult, TimeSeries


def get_local_now():
    """Получить текущее локальное время"""
    return datetime.now()


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
        summary: Optional[Dict[str, Any]] = None
    ) -> Optional[TestRun]:
        """Обновить статус тестового прогона"""
        with self.get_session() as session:
            test_run = session.query(TestRun).filter(
                TestRun.id == uuid.UUID(test_run_id)
            ).first()
            
            if test_run:
                test_run.status = status
                if status in ['completed', 'failed']:
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
