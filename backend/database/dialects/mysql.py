"""
MySQL-специфичная реализация диалекта СУБД.
"""
from typing import Any, Dict, Optional, Set

from sqlalchemy import text

from backend.database.dialects.base import DEFAULT_DBMS_METRICS, DbmsDialect


class MySQLDialect(DbmsDialect):
    """Диалект MySQL."""

    name = "mysql"
    display_name = "MySQL"
    default_port = 3306
    quote_char = "`"
    native_dump_family = "mysql"

    def get_connection_url(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> str:
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    def get_list_tables_sql(self) -> str:
        return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_type = 'BASE TABLE'
        """

    def get_columns_sql(self) -> str:
        return """
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                CONCAT_WS(' ', column_default, extra) AS column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            ORDER BY table_name, ordinal_position
        """

    def get_sample_column_values_sql(self, table: str, column: str) -> str:
        quoted_column = self.quote_identifier(column)
        return (
            f"SELECT {quoted_column} FROM {self.quote_identifier(table)} "
            f"WHERE {quoted_column} IS NOT NULL ORDER BY RAND() LIMIT :limit"
        )

    def get_primary_keys_sql(self) -> str:
        return """
            SELECT
                tc.table_name,
                kcu.column_name,
                kcu.ordinal_position
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
               AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = DATABASE()
            ORDER BY tc.table_name, kcu.ordinal_position
        """

    def get_foreign_keys_detailed_sql(self) -> str:
        return """
            SELECT
                constraint_name,
                table_name,
                column_name,
                referenced_table_name,
                referenced_column_name
            FROM information_schema.key_column_usage
            WHERE referenced_table_name IS NOT NULL
              AND table_schema = DATABASE()
            ORDER BY table_name, constraint_name, ordinal_position
        """

    def get_unique_constraints_sql(self) -> str:
        return """
            SELECT
                tc.table_name,
                kcu.column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
               AND tc.table_schema = kcu.table_schema
               AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'UNIQUE'
              AND tc.table_schema = DATABASE()
            ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
        """

    def get_table_size_sql(self, table: str) -> str:
        return f"""
            SELECT DATA_LENGTH + INDEX_LENGTH
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = '{table}'
        """

    def get_disable_constraints_sql(self) -> str:
        return "SET FOREIGN_KEY_CHECKS = 0"

    def get_enable_constraints_sql(self) -> str:
        return "SET FOREIGN_KEY_CHECKS = 1"

    def get_disable_strict_mode_sql(self) -> str:
        return "SET SESSION sql_mode = ''"

    def get_enable_strict_mode_sql(self) -> str:
        return "SET SESSION sql_mode = @@GLOBAL.sql_mode"

    def get_fk_dependencies_sql(self) -> str:
        return """
            SELECT
                TABLE_NAME,
                REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_NAME IS NOT NULL
              AND TABLE_SCHEMA = DATABASE()
        """

    def get_checksum_sql(self, table: str) -> str:
        return f"SELECT COUNT(*), MD5(CONCAT(GROUP_CONCAT(id))) FROM {self.quote_identifier(table)}"

    def extract_checksum_value(self, row: Any) -> str:
        return row[1] if row and len(row) > 1 else ""

    async def get_auto_value(self, conn, table: str) -> Optional[int]:
        sql = """
            SELECT AUTO_INCREMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
        """
        result = await conn.execute(text(sql), {"table": table})
        row = result.fetchone()
        return row[0] if row else None

    async def save_auto_values(self, conn, tables: Set[str]) -> Dict[str, Any]:
        auto_increments: Dict[str, Any] = {}
        sql = """
            SELECT AUTO_INCREMENT
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
        """
        for table in tables:
            result = await conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            if row and row[0]:
                auto_increments[table] = row[0]
        return auto_increments

    async def restore_auto_values(self, conn, values: Dict[str, Any]) -> None:
        for table, value in values.items():
            sql = f"ALTER TABLE {self.quote_identifier(table)} AUTO_INCREMENT = {value}"
            await conn.execute(text(sql))

    def get_create_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        table_name = self.quote_identifier(index_def["table_name"])
        columns_sql = self.build_columns_sql(index_def["column_names"])
        index_type = (index_def.get("index_type") or "btree").upper()
        is_unique = "UNIQUE " if index_def.get("is_unique") else ""
        sql = (
            f"CREATE {is_unique}INDEX {self.quote_identifier(index_name)} "
            f"ON {table_name} ({columns_sql})"
        )
        if index_type and index_type != "BTREE":
            sql += f" USING {index_type}"
        return sql

    def get_drop_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        table_name = self.quote_identifier(index_def["table_name"])
        return f"DROP INDEX {self.quote_identifier(index_name)} ON {table_name}"

    def get_existing_indexes_sql(self) -> str:
        return """
            SELECT
                INDEX_NAME AS index_name,
                GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') AS columns
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
            GROUP BY INDEX_NAME
        """

    async def collect_dbms_metrics(self, conn) -> Dict[str, Any]:
        metrics = dict(DEFAULT_DBMS_METRICS)
        metrics["table_sizes_mb"] = {}
        metrics["index_sizes_mb"] = {}

        async def safe_scalar(sql: str) -> float:
            try:
                result = await conn.execute(text(sql))
                row = result.fetchone()
                return float(row[0] or 0) if row else 0.0
            except Exception:
                return 0.0

        metrics["buffer_pool_hit_ratio"] = await safe_scalar("""
            SELECT
                (1 - (Innodb_buffer_pool_reads / NULLIF(Innodb_buffer_pool_read_requests, 0))) * 100
                as hit_ratio
            FROM (
                SELECT
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads') as Innodb_buffer_pool_reads,
                    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
                     WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests') as Innodb_buffer_pool_read_requests
            ) as stats
        """)
        metrics["cache_hit_ratio"] = metrics["buffer_pool_hit_ratio"]
        metrics["active_connections"] = int(await safe_scalar("""
            SELECT COUNT(*) FROM information_schema.PROCESSLIST
        """))
        metrics["lock_waits"] = int(await safe_scalar("""
            SELECT COUNT(*) FROM performance_schema.data_lock_waits
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

        metrics["total_db_size_mb"] = await safe_scalar("""
            SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / (1024 * 1024), 2) AS size_mb
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
        """)

        return metrics

    async def terminate_other_connections(self, conn, db_name: Optional[str]) -> int:
        terminated = 0
        result = await conn.execute(text("SHOW PROCESSLIST"))
        rows = result.fetchall()
        for row in rows:
            process_id = row[0]
            process_db = row[3] if len(row) > 3 else None
            process_command = row[4] if len(row) > 4 else None
            if process_command != "Sleep" and process_db == db_name:
                try:
                    await conn.execute(text(f"KILL {process_id}"))
                    terminated += 1
                except Exception:
                    pass
        return terminated
