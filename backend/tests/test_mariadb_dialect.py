"""
Unit-тесты для backend/database/dialects/mariadb.py.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.database.dialects.cache_metrics import CACHE_STATUS_NO_ACTIVITY
from backend.database.dialects.mariadb import MariaDBDialect


class _Result:
    """Простой объект результата для имитации SQLAlchemy result."""

    def __init__(self, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def fetchone(self):
        return self._one

    def __iter__(self):
        return iter(self._rows)


@pytest.mark.asyncio
async def test_collect_dbms_metrics_does_not_set_lifetime_cache_ratio():
    dialect = MariaDBDialect()
    conn = MagicMock()

    status_values = {
        "Innodb_buffer_pool_reads": 100.0,
        "Innodb_buffer_pool_read_requests": 10000.0,
        "Innodb_row_lock_waits": 7.0,
        "Innodb_deadlocks": 2.0,
    }

    async def execute_side_effect(stmt, params=None):
        sql = str(stmt)

        if "SHOW GLOBAL STATUS LIKE" in sql:
            name = sql.split("LIKE '", 1)[1].split("'", 1)[0]
            return _Result(one=(name, str(status_values[name])))

        if "COUNT(*) FROM information_schema.PROCESSLIST" in sql:
            return _Result(one=(11,))

        if "FROM information_schema.TABLES" in sql and "LIMIT 10" in sql:
            return _Result(rows=[("orders", 12.5), ("users", 8.0)])

        if "ROUND(SUM(DATA_LENGTH + INDEX_LENGTH)" in sql:
            return _Result(one=(256.75,))

        return _Result(one=(0,))

    conn.execute = AsyncMock(side_effect=execute_side_effect)

    metrics = await dialect.collect_dbms_metrics(conn)

    assert metrics["cache_hit_ratio"] is None
    assert metrics["active_connections"] == 11
    assert metrics["table_sizes_mb"]["orders"] == 12.5


@pytest.mark.asyncio
async def test_collect_dbms_metric_counters_includes_innodb_cache():
    dialect = MariaDBDialect()
    conn = MagicMock()

    status_values = {
        "Innodb_buffer_pool_reads": 100.0,
        "Innodb_buffer_pool_read_requests": 10000.0,
        "Innodb_row_lock_waits": 7.0,
        "Innodb_deadlocks": 2.0,
    }

    async def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        if "SHOW GLOBAL STATUS LIKE" in sql:
            name = sql.split("LIKE '", 1)[1].split("'", 1)[0]
            return _Result(one=(name, str(status_values[name])))
        return _Result(one=(0,))

    conn.execute = AsyncMock(side_effect=execute_side_effect)

    counters = await dialect.collect_dbms_metric_counters(conn)

    assert counters["innodb_buffer_pool_reads"] == 100
    assert counters["innodb_buffer_pool_read_requests"] == 10000
    assert counters["lock_waits_total"] == 7
    assert counters["deadlocks_total"] == 2


def test_build_final_dbms_metrics_uses_delta_for_lock_waits_and_cache():
    dialect = MariaDBDialect()

    metrics = dialect.build_final_dbms_metrics(
        latest_metrics={
            "lock_waits": 0,
            "deadlocks": 0,
        },
        start_counters={
            "innodb_buffer_pool_reads": 100,
            "innodb_buffer_pool_read_requests": 10000,
            "lock_waits_total": 10,
            "deadlocks_total": 2,
        },
        end_counters={
            "innodb_buffer_pool_reads": 150,
            "innodb_buffer_pool_read_requests": 20000,
            "lock_waits_total": 17,
            "deadlocks_total": 3,
        },
    )

    assert metrics["lock_waits"] == 7
    assert metrics["lock_waits_mode"] == "delta"
    assert metrics["deadlocks"] == 1
    assert metrics["cache_hit_ratio_raw"] == 99.5
    assert metrics["cache_hit_ratio"] == 99.5


def test_build_final_dbms_metrics_no_activity_for_zero_delta_requests():
    dialect = MariaDBDialect()

    metrics = dialect.build_final_dbms_metrics(
        latest_metrics={},
        start_counters={
            "innodb_buffer_pool_reads": 0,
            "innodb_buffer_pool_read_requests": 0,
        },
        end_counters={
            "innodb_buffer_pool_reads": 0,
            "innodb_buffer_pool_read_requests": 0,
        },
    )

    assert metrics["cache_hit_ratio"] is None
    assert metrics["cache_hit_ratio_status"] == CACHE_STATUS_NO_ACTIVITY
