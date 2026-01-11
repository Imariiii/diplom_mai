"""
SQLAlchemy модели для хранения истории тестов
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, 
    Text, JSON, BigInteger, Index, create_engine
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class TestRun(Base):
    """Модель для хранения информации о тестовом прогоне"""
    __tablename__ = 'test_runs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, running, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    # Конфигурация теста
    config = Column(JSON, nullable=False, default=dict)
    # {
    #   "db_types": ["postgresql", "mysql"],
    #   "iterations": 100,
    #   "duration": 60,
    #   "virtual_users": 10,
    #   "scenario": "mixed_light",
    #   "warmup_time": 5
    # }
    
    # Общая статистика
    summary = Column(JSON, nullable=True)
    # {
    #   "total_transactions": 1000,
    #   "overall_tps": 16.7,
    #   "total_duration": 60
    # }
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    time_series = relationship("TimeSeries", back_populates="test_run", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'config': self.config,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TestResult(Base):
    """Модель для хранения результатов теста по каждой СУБД"""
    __tablename__ = 'test_results'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey('test_runs.id', ondelete='CASCADE'), nullable=False)
    db_type = Column(String(50), nullable=False)  # postgresql, mysql
    query_id = Column(String(100), nullable=True)
    
    # Метрики производительности
    metrics = Column(JSON, nullable=False, default=dict)
    # {
    #   "avg_time_ms": 12.5,
    #   "min_time_ms": 8.2,
    #   "max_time_ms": 45.3,
    #   "p50_time_ms": 11.0,
    #   "p95_time_ms": 25.0,
    #   "p99_time_ms": 40.0,
    #   "tps": 80.5,
    #   "throughput": 80.5,
    #   "successful": 950,
    #   "failed": 50,
    #   "error_rate": 5.0
    # }
    
    # Системные метрики
    system_metrics = Column(JSON, nullable=True)
    # {
    #   "cpu_usage": 45.5,
    #   "memory_usage_mb": 2048,
    #   "memory_usage_percent": 50.0,
    #   "disk_iops": 1500
    # }
    
    # Внутренние метрики СУБД
    dbms_metrics = Column(JSON, nullable=True)
    # {
    #   "cache_hit_ratio": 95.5,
    #   "buffer_pool_hit_ratio": 98.0,
    #   "lock_waits": 5,
    #   "deadlocks": 0,
    #   "active_connections": 10,
    #   "total_db_size_mb": 512.5
    # }
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    test_run = relationship("TestRun", back_populates="results")
    
    # Indexes
    __table_args__ = (
        Index('idx_test_results_test_run_id', 'test_run_id'),
        Index('idx_test_results_db_type', 'db_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'test_run_id': str(self.test_run_id),
            'db_type': self.db_type,
            'query_id': self.query_id,
            'metrics': self.metrics,
            'system_metrics': self.system_metrics,
            'dbms_metrics': self.dbms_metrics,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TimeSeries(Base):
    """Модель для хранения временных рядов метрик (для графиков)"""
    __tablename__ = 'time_series'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey('test_runs.id', ondelete='CASCADE'), nullable=False)
    db_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Метрики в реальном времени
    response_time = Column(Float, nullable=True)
    tps = Column(Float, nullable=True)
    throughput = Column(Float, nullable=True)
    active_connections = Column(Integer, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Системные метрики
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    disk_iops = Column(Float, nullable=True)
    network_in = Column(Float, nullable=True)
    network_out = Column(Float, nullable=True)
    
    # Relationships
    test_run = relationship("TestRun", back_populates="time_series")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_time_series_test_run_id', 'test_run_id'),
        Index('idx_time_series_db_type', 'db_type'),
        Index('idx_time_series_timestamp', 'timestamp'),
        Index('idx_time_series_composite', 'test_run_id', 'db_type', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'test_run_id': str(self.test_run_id),
            'db_type': self.db_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'response_time': self.response_time,
            'tps': self.tps,
            'throughput': self.throughput,
            'active_connections': self.active_connections,
            'error_count': self.error_count,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_usage_mb': self.memory_usage_mb,
            'disk_iops': self.disk_iops,
            'network_in': self.network_in,
            'network_out': self.network_out,
        }


def init_db(database_url: str):
    """Инициализация базы данных и создание таблиц"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Создание сессии для работы с БД"""
    Session = sessionmaker(bind=engine)
    return Session()
