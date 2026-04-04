"""
SQLAlchemy модели для хранения истории тестов
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
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
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
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
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    time_series = relationship("TimeSeries", back_populates="test_run", cascade="all, delete-orphan")
    
    # Restore-related fields
    has_write_operations = Column(String(1), nullable=False, default='f')  # 't' - есть write-операции
    affected_tables = Column(JSON, nullable=True)  # ["film", "customer"]
    auto_restore_enabled = Column(String(1), nullable=False, default='t')  # 't' - авто-восстановление включено
    restore_status = Column(String(50), nullable=True)  # pending/success/failed/skipped/null
    restore_duration_ms = Column(Float, nullable=True)
    restore_verified = Column(String(1), nullable=True)  # 't'/'f' - верификация прошла
    restore_errors = Column(JSON, nullable=True)  # Список ошибок
    
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
            # Restore fields
            'has_write_operations': self.has_write_operations == 't',
            'affected_tables': self.affected_tables,
            'auto_restore_enabled': self.auto_restore_enabled == 't',
            'restore_status': self.restore_status,
            'restore_duration_ms': self.restore_duration_ms,
            'restore_verified': self.restore_verified == 't' if self.restore_verified else None,
            'restore_errors': self.restore_errors,
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
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
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
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
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


class DatabaseConnectionConfig(Base):
    """Модель для хранения конфигурации подключений к тестируемым БД"""
    __tablename__ = 'db_connection_configs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    dbms_type = Column(String(50), nullable=False)  # mysql, postgresql
    group = Column(String(100), nullable=True, default='default')  # Группа подключений (production, staging, local)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    user = Column(String(100), nullable=False)
    password_encrypted = Column(Text, nullable=False)
    database = Column(String(100), nullable=False)
    is_active = Column(String(1), nullable=False, default='t')  # 't' - активно, 'f' - неактивно
    extra_params = Column(JSON, nullable=True, default=dict)  # Дополнительные параметры (ssl, timeout и т.д.)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('idx_db_conn_configs_dbms_type', 'dbms_type'),
        Index('idx_db_conn_configs_group', 'group'),
        Index('idx_db_conn_configs_active', 'is_active'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'dbms_type': self.dbms_type,
            'group': self.group,
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'database': self.database,
            'is_active': self.is_active == 't',
            'extra_params': self.extra_params,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_connection_dict(self, decrypted_password: str) -> Dict[str, Any]:
        """Словарь для построения строки подключения (с расшифрованным паролем)"""
        return {
            'id': str(self.id),
            'name': self.name,
            'dbms_type': self.dbms_type,
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'password': decrypted_password,
            'database': self.database,
            'extra_params': self.extra_params or {},
        }


class TestScenario(Base):
    """Модель для хранения сценариев тестирования"""
    __tablename__ = 'test_scenarios'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(50), nullable=False)  # read_only, write_only, mixed_light, mixed_heavy, oltp, olap, custom
    is_builtin = Column(String(1), nullable=False, default='f')  # 't' - системный (нельзя удалить), 'f' - пользовательский
    is_active = Column(String(1), nullable=False, default='t')  # 't' - активен, 'f' - неактивен
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    queries = relationship("ScenarioQuery", back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioQuery.order_index")
    
    # Indexes
    __table_args__ = (
        Index('idx_test_scenarios_type', 'scenario_type'),
        Index('idx_test_scenarios_builtin', 'is_builtin'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'scenario_type': self.scenario_type,
            'is_builtin': self.is_builtin == 't',
            'is_active': self.is_active == 't',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'queries': [q.to_dict() for q in self.queries] if self.queries else [],
        }


class ScenarioQuery(Base):
    """Модель для хранения SQL-запросов в сценарии"""
    __tablename__ = 'scenario_queries'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey('test_scenarios.id', ondelete='CASCADE'), nullable=False)
    sql_template = Column(Text, nullable=False)  # SQL с placeholders: "SELECT * FROM film WHERE film_id = {film_id}"
    query_type = Column(String(20), nullable=False)  # select, insert, update, delete
    weight = Column(Integer, nullable=False, default=1)  # Вес для распределения нагрузки (1-100)
    order_index = Column(Integer, nullable=False, default=0)  # Порядок выполнения
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    scenario = relationship("TestScenario", back_populates="queries")
    params = relationship("ScenarioParam", back_populates="query", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_scenario_queries_scenario_id', 'scenario_id'),
        Index('idx_scenario_queries_type', 'query_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'scenario_id': str(self.scenario_id),
            'sql_template': self.sql_template,
            'query_type': self.query_type,
            'weight': self.weight,
            'order_index': self.order_index,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'params': [p.to_dict() for p in self.params] if self.params else [],
        }


class ScenarioParam(Base):
    """Модель для хранения параметров SQL-запросов"""
    __tablename__ = 'scenario_params'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey('scenario_queries.id', ondelete='CASCADE'), nullable=False)
    param_name = Column(String(100), nullable=False)  # Имя placeholder'а: "film_id"
    param_type = Column(String(50), nullable=False)  # random_int, random_string, random_date, sequential_int, uuid, random_from_table
    # Для числовых типов
    min_value = Column(Integer, nullable=True)
    max_value = Column(Integer, nullable=True)
    # Для строковых типов
    string_pattern = Column(String(255), nullable=True)  # Например: "user_{random}"
    string_length = Column(Integer, nullable=True)  # Длина случайной строки
    # Для random_from_table - выбор случайного ID из таблицы
    table_ref = Column(String(100), nullable=True)  # Таблица: "film"
    column_ref = Column(String(100), nullable=True)  # Колонка: "film_id"
    # Для sequential_int
    current_value = Column(Integer, nullable=True, default=0)  # Текущее значение счётчика
    step = Column(Integer, nullable=True, default=1)  # Шаг инкремента
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    query = relationship("ScenarioQuery", back_populates="params")
    
    # Indexes
    __table_args__ = (
        Index('idx_scenario_params_query_id', 'query_id'),
        Index('idx_scenario_params_name', 'param_name'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'query_id': str(self.query_id),
            'param_name': self.param_name,
            'param_type': self.param_type,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'string_pattern': self.string_pattern,
            'string_length': self.string_length,
            'table_ref': self.table_ref,
            'column_ref': self.column_ref,
            'current_value': self.current_value,
            'step': self.step,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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
