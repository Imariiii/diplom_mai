"""
SQLAlchemy модели для хранения истории тестов
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from backend.core.summary_utils import sanitize_test_summary
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey,
    Text, JSON, BigInteger, Index, create_engine, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class LogicalDatabase(Base):
    """Логическая база данных — датасет / модель данных без привязки к конкретной СУБД."""
    __tablename__ = 'logical_databases'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    schema_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey('schema_profiles.id', ondelete='SET NULL'),
        nullable=True,
    )
    reference_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey('db_connection_configs.id', ondelete='SET NULL'),
        nullable=True,
    )
    profile_status = Column(String(30), nullable=False, default='draft')
    compatibility_status = Column(String(30), nullable=False, default='unknown')
    compatibility_report = Column(JSON, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    schema_profile = relationship(
        "SchemaProfile",
        back_populates="logical_databases",
        foreign_keys=[schema_profile_id],
    )
    connections = relationship(
        "DatabaseConnectionConfig",
        back_populates="logical_database",
        foreign_keys="DatabaseConnectionConfig.logical_database_id",
    )
    reference_connection = relationship(
        "DatabaseConnectionConfig",
        foreign_keys=[reference_connection_id],
        post_update=True,
    )

    __table_args__ = (
        Index('idx_logical_databases_name', 'name'),
        Index('idx_logical_databases_schema_profile_id', 'schema_profile_id'),
        Index('idx_logical_databases_reference_connection_id', 'reference_connection_id'),
        Index('idx_logical_databases_profile_status', 'profile_status'),
        Index('idx_logical_databases_compatibility_status', 'compatibility_status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'schema_profile_id': str(self.schema_profile_id) if self.schema_profile_id else None,
            'schema_profile_name': self.schema_profile.name if self.schema_profile else None,
            'reference_connection_id': str(self.reference_connection_id) if self.reference_connection_id else None,
            'reference_connection_name': self.reference_connection.name if self.reference_connection else None,
            'profile_status': self.profile_status,
            'compatibility_status': self.compatibility_status,
            'compatibility_report': self.compatibility_report,
            'validated_at': self.validated_at.isoformat() if self.validated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SchemaProfile(Base):
    """Профиль модели данных для группы совместимых БД."""
    __tablename__ = 'schema_profiles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    detection_mode = Column(String(50), nullable=False, default='hybrid')
    reference_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey('db_connection_configs.id', ondelete='SET NULL'),
        nullable=True,
    )
    is_builtin = Column(String(1), nullable=False, default='f')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reference_connection = relationship(
        "DatabaseConnectionConfig",
        foreign_keys=[reference_connection_id],
        post_update=True,
    )
    connections = relationship(
        "DatabaseConnectionConfig",
        back_populates="schema_profile",
        foreign_keys="DatabaseConnectionConfig.schema_profile_id",
    )
    logical_databases = relationship(
        "LogicalDatabase",
        back_populates="schema_profile",
        foreign_keys="LogicalDatabase.schema_profile_id",
    )
    bundles = relationship("ScenarioBundle", back_populates="schema_profile", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_schema_profiles_name', 'name'),
        Index('idx_schema_profiles_builtin', 'is_builtin'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'detection_mode': self.detection_mode,
            'reference_connection_id': str(self.reference_connection_id) if self.reference_connection_id else None,
            'is_builtin': self.is_builtin == 't',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ScenarioTemplate(Base):
    """Логический шаблон сценария нагрузки."""
    __tablename__ = 'scenario_templates'

    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_builtin = Column(String(1), nullable=False, default='t')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    bundles = relationship("ScenarioBundle", back_populates="scenario_template")

    __table_args__ = (
        Index('idx_scenario_templates_builtin', 'is_builtin'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_builtin': self.is_builtin == 't',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


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
    #   "total_duration": 60
    # }
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")
    time_series = relationship("TimeSeries", back_populates="test_run", cascade="all, delete-orphan")
    metric_samples = relationship("MetricSample", back_populates="test_run", cascade="all, delete-orphan")
    
    # Привязка к логической базе данных
    logical_database_id = Column(
        UUID(as_uuid=True),
        ForeignKey('logical_databases.id', ondelete='SET NULL'),
        nullable=True,
    )

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
            'summary': sanitize_test_summary(self.summary),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'logical_database_id': str(self.logical_database_id) if self.logical_database_id else None,
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
    connection_key = Column(String(255), nullable=True)
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
            'connection_key': self.connection_key,
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


class MetricSample(Base):
    """Модель для хранения raw/semiraw метрик теста"""
    __tablename__ = 'metric_samples'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey('test_runs.id', ondelete='CASCADE'), nullable=False)
    db_type = Column(String(50), nullable=False)
    connection_key = Column(String(255), nullable=True)
    query_id = Column(String(100), nullable=True)
    sample_type = Column(String(50), nullable=False)  # request_latency | throughput_window | throughput_realtime
    timestamp = Column(DateTime(timezone=True), nullable=False)
    latency_ms = Column(Float, nullable=True)
    throughput = Column(Float, nullable=True)
    tps = Column(Float, nullable=True)
    is_error = Column(String(1), nullable=False, default='f')
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    test_run = relationship("TestRun", back_populates="metric_samples")

    __table_args__ = (
        Index('idx_metric_samples_test_run_id', 'test_run_id'),
        Index('idx_metric_samples_db_type', 'db_type'),
        Index('idx_metric_samples_query_id', 'query_id'),
        Index('idx_metric_samples_timestamp', 'timestamp'),
        Index('idx_metric_samples_composite', 'test_run_id', 'db_type', 'timestamp'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'test_run_id': str(self.test_run_id),
            'db_type': self.db_type,
            'connection_key': self.connection_key,
            'query_id': self.query_id,
            'sample_type': self.sample_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'latency_ms': self.latency_ms,
            'throughput': self.throughput,
            'tps': self.tps,
            'is_error': self.is_error == 't',
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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
    logical_database_id = Column(
        UUID(as_uuid=True),
        ForeignKey('logical_databases.id', ondelete='SET NULL'),
        nullable=True,
    )
    schema_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey('schema_profiles.id', ondelete='SET NULL'),
        nullable=True,
    )
    detected_profile_name = Column(String(100), nullable=True)
    profile_confidence = Column(Float, nullable=True)
    profile_source = Column(String(20), nullable=True, default='auto')
    is_active = Column(String(1), nullable=False, default='t')  # 't' - активно, 'f' - неактивно
    extra_params = Column(JSON, nullable=True, default=dict)  # Дополнительные параметры (ssl, timeout и т.д.)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    logical_database = relationship(
        "LogicalDatabase",
        back_populates="connections",
        foreign_keys=[logical_database_id],
    )
    schema_profile = relationship(
        "SchemaProfile",
        back_populates="connections",
        foreign_keys=[schema_profile_id],
    )

    # Indexes
    __table_args__ = (
        Index('idx_db_conn_configs_dbms_type', 'dbms_type'),
        Index('idx_db_conn_configs_group', 'group'),
        Index('idx_db_conn_configs_active', 'is_active'),
        Index('idx_db_conn_configs_schema_profile_id', 'schema_profile_id'),
        Index('idx_db_conn_configs_logical_db_id', 'logical_database_id'),
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
            'logical_database_id': str(self.logical_database_id) if self.logical_database_id else None,
            'logical_database_name': self.logical_database.name if self.logical_database else None,
            'schema_profile_id': str(self.schema_profile_id) if self.schema_profile_id else None,
            'schema_profile_name': self.schema_profile.name if self.schema_profile else None,
            'detected_profile_name': self.detected_profile_name,
            'profile_confidence': self.profile_confidence,
            'profile_source': self.profile_source,
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
            'schema_profile_id': str(self.schema_profile_id) if self.schema_profile_id else None,
            'schema_profile_name': self.schema_profile.name if self.schema_profile else None,
            'detected_profile_name': self.detected_profile_name,
            'profile_confidence': self.profile_confidence,
            'profile_source': self.profile_source,
            'extra_params': self.extra_params or {},
        }


class ScenarioBundle(Base):
    """SQL bundle-вариант для пары профиль + логический сценарий."""
    __tablename__ = 'scenario_bundles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_profile_id = Column(UUID(as_uuid=True), ForeignKey('schema_profiles.id', ondelete='CASCADE'), nullable=False)
    scenario_template_id = Column(String(50), ForeignKey('scenario_templates.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    generation_source = Column(String(50), nullable=False, default='generated_from_reference')
    is_builtin = Column(String(1), nullable=False, default='f')
    is_active = Column(String(1), nullable=False, default='t')
    generated_from_connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey('db_connection_configs.id', ondelete='SET NULL'),
        nullable=True,
    )
    workload_mode = Column(String(20), nullable=False, default='query')
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    schema_profile = relationship("SchemaProfile", back_populates="bundles")
    scenario_template = relationship("ScenarioTemplate", back_populates="bundles")
    generated_from_connection = relationship("DatabaseConnectionConfig", foreign_keys=[generated_from_connection_id])
    queries = relationship(
        "ScenarioBundleQuery",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="ScenarioBundleQuery.order_index",
    )
    transactions = relationship(
        "ScenarioBundleTransaction",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="ScenarioBundleTransaction.order_index",
    )
    indexes = relationship("ScenarioBundleIndex", back_populates="bundle", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_scenario_bundles_profile_id', 'schema_profile_id'),
        Index('idx_scenario_bundles_template_id', 'scenario_template_id'),
        Index('idx_scenario_bundles_builtin', 'is_builtin'),
        Index('idx_scenario_bundles_active', 'is_active'),
        Index(
            'uq_scenario_bundles_profile_template_active',
            'schema_profile_id',
            'scenario_template_id',
            unique=True,
            postgresql_where=text("is_active = 't'"),
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'schema_profile_id': str(self.schema_profile_id),
            'schema_profile_name': self.schema_profile.name if self.schema_profile else None,
            'scenario_template_id': self.scenario_template_id,
            'scenario_template_name': self.scenario_template.name if self.scenario_template else None,
            'name': self.name,
            'description': self.description,
            'generation_source': self.generation_source,
            'is_builtin': self.is_builtin == 't',
            'is_active': self.is_active == 't',
            'generated_from_connection_id': (
                str(self.generated_from_connection_id) if self.generated_from_connection_id else None
            ),
            'workload_mode': self.workload_mode or 'query',
            'primary_rate_unit': 'tps' if (self.workload_mode or 'query') == 'transaction' else 'qps',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'queries': [query.to_dict() for query in self.queries] if self.queries else [],
            'transactions': [tx.to_dict() for tx in self.transactions] if self.transactions else [],
            'indexes': [index.to_dict() for index in self.indexes] if self.indexes else [],
        }


class ScenarioBundleQuery(Base):
    """SQL-запрос внутри канонического bundle."""
    __tablename__ = 'scenario_bundle_queries'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey('scenario_bundles.id', ondelete='CASCADE'), nullable=False)
    sql_template = Column(Text, nullable=False)
    query_type = Column(String(20), nullable=False)
    weight = Column(Integer, nullable=False, default=1)
    order_index = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    bundle = relationship("ScenarioBundle", back_populates="queries")
    params = relationship("ScenarioBundleParam", back_populates="query", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_scenario_bundle_queries_bundle_id', 'bundle_id'),
        Index('idx_scenario_bundle_queries_type', 'query_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bundle_id': str(self.bundle_id),
            'sql_template': self.sql_template,
            'query_type': self.query_type,
            'weight': self.weight,
            'order_index': self.order_index,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'params': [param.to_dict() for param in self.params] if self.params else [],
        }


class ScenarioBundleParam(Base):
    """Параметры запроса внутри bundle."""
    __tablename__ = 'scenario_bundle_params'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey('scenario_bundle_queries.id', ondelete='CASCADE'), nullable=False)
    param_name = Column(String(100), nullable=False)
    param_type = Column(String(50), nullable=False)
    min_value = Column(Integer, nullable=True)
    max_value = Column(Integer, nullable=True)
    string_pattern = Column(String(255), nullable=True)
    string_length = Column(Integer, nullable=True)
    table_ref = Column(String(100), nullable=True)
    column_ref = Column(String(100), nullable=True)
    fixed_value = Column(String(255), nullable=True)
    current_value = Column(Integer, nullable=True, default=0)
    step = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    query = relationship("ScenarioBundleQuery", back_populates="params")

    __table_args__ = (
        Index('idx_scenario_bundle_params_query_id', 'query_id'),
        Index('idx_scenario_bundle_params_name', 'param_name'),
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
            'fixed_value': self.fixed_value,
            'current_value': self.current_value,
            'step': self.step,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioBundleTransaction(Base):
    """Пользовательская транзакция внутри transaction bundle."""
    __tablename__ = 'scenario_bundle_transactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey('scenario_bundles.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    weight = Column(Integer, nullable=False, default=1)
    order_index = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    bundle = relationship("ScenarioBundle", back_populates="transactions")
    steps = relationship(
        "ScenarioBundleTransactionStep",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="ScenarioBundleTransactionStep.order_index",
    )
    params = relationship(
        "ScenarioBundleTransactionParam",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index('idx_scenario_bundle_transactions_bundle_id', 'bundle_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bundle_id': str(self.bundle_id),
            'name': self.name,
            'weight': self.weight,
            'order_index': self.order_index,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'steps': [step.to_dict() for step in self.steps] if self.steps else [],
            'params': [param.to_dict() for param in self.params] if self.params else [],
        }


class ScenarioBundleTransactionStep(Base):
    """Шаг SQL внутри транзакции bundle."""
    __tablename__ = 'scenario_bundle_transaction_steps'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey('scenario_bundle_transactions.id', ondelete='CASCADE'),
        nullable=False,
    )
    sql_template = Column(Text, nullable=False)
    query_type = Column(String(20), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transaction = relationship("ScenarioBundleTransaction", back_populates="steps")

    __table_args__ = (
        Index('idx_scenario_bundle_transaction_steps_tx_id', 'transaction_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transaction_id': str(self.transaction_id),
            'sql_template': self.sql_template,
            'query_type': self.query_type,
            'order_index': self.order_index,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioBundleTransactionParam(Base):
    """Параметры транзакции (общие для всех шагов в рамках одного выполнения)."""
    __tablename__ = 'scenario_bundle_transaction_params'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey('scenario_bundle_transactions.id', ondelete='CASCADE'),
        nullable=False,
    )
    param_name = Column(String(100), nullable=False)
    param_type = Column(String(50), nullable=False)
    min_value = Column(Integer, nullable=True)
    max_value = Column(Integer, nullable=True)
    string_pattern = Column(String(255), nullable=True)
    string_length = Column(Integer, nullable=True)
    table_ref = Column(String(100), nullable=True)
    column_ref = Column(String(100), nullable=True)
    fixed_value = Column(String(255), nullable=True)
    current_value = Column(Integer, nullable=True, default=0)
    step = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    transaction = relationship("ScenarioBundleTransaction", back_populates="params")

    __table_args__ = (
        Index('idx_scenario_bundle_transaction_params_tx_id', 'transaction_id'),
        Index('idx_scenario_bundle_transaction_params_name', 'param_name'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transaction_id': str(self.transaction_id),
            'param_name': self.param_name,
            'param_type': self.param_type,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'string_pattern': self.string_pattern,
            'string_length': self.string_length,
            'table_ref': self.table_ref,
            'column_ref': self.column_ref,
            'fixed_value': self.fixed_value,
            'current_value': self.current_value,
            'step': self.step,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScenarioBundleIndex(Base):
    """Индексы, связанные с bundle."""
    __tablename__ = 'scenario_bundle_indexes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bundle_id = Column(UUID(as_uuid=True), ForeignKey('scenario_bundles.id', ondelete='CASCADE'), nullable=False)
    table_name = Column(String(100), nullable=False)
    column_names = Column(String(500), nullable=False)
    index_type = Column(String(50), nullable=False, default='btree')
    index_name = Column(String(255), nullable=True)
    is_unique = Column(String(1), nullable=False, default='f')
    condition = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    bundle = relationship("ScenarioBundle", back_populates="indexes")

    __table_args__ = (
        Index('idx_scenario_bundle_indexes_bundle_id', 'bundle_id'),
        Index('idx_scenario_bundle_indexes_table_name', 'table_name'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'bundle_id': str(self.bundle_id),
            'table_name': self.table_name,
            'column_names': self.column_names,
            'index_type': self.index_type,
            'index_name': self.index_name,
            'is_unique': self.is_unique == 't',
            'condition': self.condition,
            'description': self.description,
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
