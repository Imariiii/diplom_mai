"""
Миграция 001: Создание всех таблиц схемы

Таблицы:
  - test_runs          — история тестовых прогонов
  - test_results       — результаты по каждой СУБД
  - time_series        — временные ряды метрик
  - metric_samples     — raw/semiraw sample-метрики
  - db_connection_configs — конфигурации подключений к тестируемым БД
  - test_scenarios     — сценарии тестирования
  - scenario_queries   — SQL-запросы в сценариях
  - scenario_params    — параметры SQL-запросов
"""
from sqlalchemy import text


def upgrade(conn) -> None:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS test_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ,
            config JSON NOT NULL DEFAULT '{}',
            summary JSON,
            created_at TIMESTAMPTZ DEFAULT now(),
            has_write_operations VARCHAR(1) NOT NULL DEFAULT 'f',
            affected_tables JSON,
            auto_restore_enabled VARCHAR(1) NOT NULL DEFAULT 't',
            restore_status VARCHAR(50),
            restore_duration_ms FLOAT,
            restore_verified VARCHAR(1),
            restore_errors JSON
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS test_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
            db_type VARCHAR(50) NOT NULL,
            query_id VARCHAR(100),
            metrics JSON NOT NULL DEFAULT '{}',
            system_metrics JSON,
            dbms_metrics JSON,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_test_results_test_run_id ON test_results(test_run_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_test_results_db_type ON test_results(db_type)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS time_series (
            id BIGSERIAL PRIMARY KEY,
            test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
            db_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            response_time FLOAT,
            tps FLOAT,
            throughput FLOAT,
            active_connections INTEGER,
            error_count INTEGER DEFAULT 0,
            cpu_usage FLOAT,
            memory_usage FLOAT,
            memory_usage_mb FLOAT,
            disk_iops FLOAT,
            network_in FLOAT,
            network_out FLOAT
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_time_series_test_run_id ON time_series(test_run_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_time_series_db_type ON time_series(db_type)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_time_series_timestamp ON time_series(timestamp)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_time_series_composite ON time_series(test_run_id, db_type, timestamp)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS metric_samples (
            id BIGSERIAL PRIMARY KEY,
            test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
            db_type VARCHAR(50) NOT NULL,
            connection_key VARCHAR(255),
            query_id VARCHAR(100),
            sample_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            latency_ms FLOAT,
            throughput FLOAT,
            tps FLOAT,
            is_error VARCHAR(1) NOT NULL DEFAULT 'f',
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_metric_samples_test_run_id ON metric_samples(test_run_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_metric_samples_db_type ON metric_samples(db_type)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_metric_samples_query_id ON metric_samples(query_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_metric_samples_timestamp ON metric_samples(timestamp)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_metric_samples_composite ON metric_samples(test_run_id, db_type, timestamp)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS db_connection_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            dbms_type VARCHAR(50) NOT NULL,
            "group" VARCHAR(100) DEFAULT 'default',
            host VARCHAR(255) NOT NULL,
            port INTEGER NOT NULL,
            "user" VARCHAR(100) NOT NULL,
            password_encrypted TEXT NOT NULL,
            database VARCHAR(100) NOT NULL,
            is_active VARCHAR(1) NOT NULL DEFAULT 't',
            extra_params JSON DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_db_conn_configs_dbms_type ON db_connection_configs(dbms_type)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_db_conn_configs_group ON db_connection_configs("group")
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_db_conn_configs_active ON db_connection_configs(is_active)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS test_scenarios (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            scenario_type VARCHAR(50) NOT NULL,
            is_builtin VARCHAR(1) NOT NULL DEFAULT 'f',
            is_active VARCHAR(1) NOT NULL DEFAULT 't',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_test_scenarios_type ON test_scenarios(scenario_type)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_test_scenarios_builtin ON test_scenarios(is_builtin)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS scenario_queries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scenario_id UUID NOT NULL REFERENCES test_scenarios(id) ON DELETE CASCADE,
            sql_template TEXT NOT NULL,
            query_type VARCHAR(20) NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1,
            order_index INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_scenario_queries_scenario_id ON scenario_queries(scenario_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_scenario_queries_type ON scenario_queries(query_type)
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS scenario_params (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            query_id UUID NOT NULL REFERENCES scenario_queries(id) ON DELETE CASCADE,
            param_name VARCHAR(100) NOT NULL,
            param_type VARCHAR(50) NOT NULL,
            min_value INTEGER,
            max_value INTEGER,
            string_pattern VARCHAR(255),
            string_length INTEGER,
            table_ref VARCHAR(100),
            column_ref VARCHAR(100),
            current_value INTEGER DEFAULT 0,
            step INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))

    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_scenario_params_query_id ON scenario_params(query_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_scenario_params_name ON scenario_params(param_name)
    """))
