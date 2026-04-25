"""
Unit-тесты для backend/database/dialects/mariadb.py.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

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
async def test_collect_dbms_metrics_uses_status_counters_and_computes_ratios():
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

    assert round(metrics["buffer_pool_hit_ratio"], 2) == 99.0
    assert round(metrics["cache_hit_ratio"], 2) == 99.0
    assert metrics["active_connections"] == 11
    assert metrics["lock_waits"] == 0
    assert metrics["deadlocks"] == 0
    assert metrics["table_sizes_mb"]["orders"] == 12.5
    assert metrics["table_sizes_mb"]["users"] == 8.0
    assert metrics["total_db_size_mb"] == 256.75

    counters = await dialect.collect_dbms_metric_counters(conn)

    assert counters["lock_waits_total"] == 7
    assert counters["deadlocks_total"] == 2


@pytest.mark.asyncio
async def test_collect_dbms_metrics_fallbacks_to_information_schema_when_show_fails():
    dialect = MariaDBDialect()
    conn = MagicMock()

    fallback_values = {
        "Innodb_buffer_pool_reads": 50.0,
        "Innodb_buffer_pool_read_requests": 5000.0,
        "Innodb_row_lock_waits": 3.0,
        "Innodb_deadlocks": 1.0,
    }

    async def execute_side_effect(stmt, params=None):
        sql = str(stmt)

        if "SHOW GLOBAL STATUS LIKE" in sql:
            raise RuntimeError("SHOW GLOBAL STATUS denied")

        if "FROM information_schema.GLOBAL_STATUS" in sql:
            status_name = params["status_name"]
            return _Result(one=(str(fallback_values[status_name]),))

        if "COUNT(*) FROM information_schema.PROCESSLIST" in sql:
            return _Result(one=(4,))

        if "FROM information_schema.TABLES" in sql and "LIMIT 10" in sql:
            return _Result(rows=[])

        if "ROUND(SUM(DATA_LENGTH + INDEX_LENGTH)" in sql:
            return _Result(one=(10.0,))

        return _Result(one=(0,))

    conn.execute = AsyncMock(side_effect=execute_side_effect)

    metrics = await dialect.collect_dbms_metrics(conn)

    assert round(metrics["buffer_pool_hit_ratio"], 2) == 99.0
    assert round(metrics["cache_hit_ratio"], 2) == 99.0
    assert metrics["active_connections"] == 4
    assert metrics["lock_waits"] == 0
    assert metrics["deadlocks"] == 0
    assert metrics["total_db_size_mb"] == 10.0

    counters = await dialect.collect_dbms_metric_counters(conn)

    assert counters["lock_waits_total"] == 3
    assert counters["deadlocks_total"] == 1


def test_build_final_dbms_metrics_uses_delta_for_lock_waits_and_deadlocks():
    dialect = MariaDBDialect()

    metrics = dialect.build_final_dbms_metrics(
        latest_metrics={
            "cache_hit_ratio": 99.0,
            "buffer_pool_hit_ratio": 99.0,
            "lock_waits": 0,
            "deadlocks": 0,
        },
        start_counters={"lock_waits_total": 10, "deadlocks_total": 2},
        end_counters={"lock_waits_total": 17, "deadlocks_total": 3},
    )

    assert metrics["lock_waits"] == 7
    assert metrics["lock_waits_mode"] == "delta"
    assert metrics["deadlocks"] == 1
    assert metrics["deadlocks_mode"] == "delta"
