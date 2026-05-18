"""
MariaDB-специфичная реализация диалекта СУБД.
"""
from typing import Any, Dict

from sqlalchemy import text

from backend.database.dialects.base import DEFAULT_DBMS_METRICS
from backend.database.dialects.mysql import MySQLDialect


class MariaDBDialect(MySQLDialect):
    """Диалект MariaDB поверх MySQL-совместимого async driver."""

    name = "mariadb"
    display_name = "MariaDB"

    def get_connection_url(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> str:
        # Для asyncio SQLAlchemy штатно поддерживает aiomysql через mysql-dialect,
        # а тип mariadb сохраняется отдельно на уровне конфигурации проекта.
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    async def _get_global_status_value(self, conn, status_name: str) -> float:
        """Получить числовое значение status-переменной MariaDB."""
        try:
            result = await conn.execute(
                text(f"SHOW GLOBAL STATUS LIKE '{status_name}'")
            )
            row = result.fetchone()
            if row and len(row) > 1:
                return float(row[1] or 0)
        except Exception:
            pass

        # Fallback для конфигураций, где SHOW ограничен.
        try:
            result = await conn.execute(
                text(
                    """
                    SELECT VARIABLE_VALUE
                    FROM information_schema.GLOBAL_STATUS
                    WHERE VARIABLE_NAME = :status_name
                    """
                ),
                {"status_name": status_name},
            )
            row = result.fetchone()
            return float(row[0] or 0) if row else 0.0
        except Exception:
            return 0.0

    async def _get_global_variable_value(self, conn, variable_name: str) -> float:
        """Получить числовое значение config-переменной MariaDB."""
        try:
            result = await conn.execute(
                text(f"SHOW GLOBAL VARIABLES LIKE '{variable_name}'")
            )
            row = result.fetchone()
            if row and len(row) > 1:
                return float(row[1] or 0)
        except Exception:
            pass

        try:
            result = await conn.execute(
                text(
                    """
                    SELECT VARIABLE_VALUE
                    FROM information_schema.GLOBAL_VARIABLES
                    WHERE VARIABLE_NAME = :variable_name
                    """
                ),
                {"variable_name": variable_name},
            )
            row = result.fetchone()
            return float(row[0] or 0) if row else 0.0
        except Exception:
            return 0.0

    async def collect_dbms_metrics(self, conn) -> Dict[str, Any]:
        """
        Собрать внутренние метрики MariaDB.

        В MariaDB часто недоступны performance_schema таблицы MySQL 8,
        поэтому читаем счётчики через SHOW GLOBAL STATUS с fallback.
        """
        metrics = dict(DEFAULT_DBMS_METRICS)
        metrics["table_sizes_mb"] = {}
        metrics["index_sizes_mb"] = {}
        metrics["buffer_size_label"] = "InnoDB buffer pool"

        async def _safe_scalar(sql: str) -> float:
            try:
                result = await conn.execute(text(sql))
                row = result.fetchone()
                return float(row[0] or 0) if row else 0.0
            except Exception:
                return 0.0

        metrics["active_connections"] = int(await _safe_scalar("""
            SELECT COUNT(*) FROM information_schema.PROCESSLIST
        """))

        metrics["lock_waits"] = int(await _safe_scalar("""
            SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS
        """))

        try:
            result = await conn.execute(text("""
                SELECT TABLE_NAME,
                       ROUND((DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                ORDER BY (DATA_LENGTH + INDEX_LENGTH) DESC
                LIMIT 10
            """))
            for row in result:
                metrics["table_sizes_mb"][row[0]] = float(row[1] or 0)
        except Exception:
            pass

        metrics["total_db_size_mb"] = await _safe_scalar("""
            SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
        """)
        metrics["buffer_size_mb"] = (
            await self._get_global_variable_value(conn, "innodb_buffer_pool_size")
        ) / (1024 * 1024)

        return metrics

    async def collect_dbms_metric_counters(self, conn) -> Dict[str, Any]:
        """Собрать накопительные счётчики MariaDB для финального delta-расчёта."""
        return {
            "innodb_buffer_pool_reads": int(
                await self._get_global_status_value(conn, "Innodb_buffer_pool_reads")
            ),
            "innodb_buffer_pool_read_requests": int(
                await self._get_global_status_value(conn, "Innodb_buffer_pool_read_requests")
            ),
            "lock_waits_total": int(await self._get_global_status_value(conn, "Innodb_row_lock_waits")),
            "deadlocks_total": int(await self._get_global_status_value(conn, "Innodb_deadlocks")),
        }
