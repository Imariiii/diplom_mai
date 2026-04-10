"""
PostgreSQL-специфичная реализация диалекта СУБД.
"""
from typing import Any, Dict, Optional, Set

from sqlalchemy import text

from backend.database.dialects.base import DEFAULT_DBMS_METRICS, DbmsDialect


class PostgreSQLDialect(DbmsDialect):
    """Диалект PostgreSQL."""

    name = "postgresql"
    display_name = "PostgreSQL"
    default_port = 5432
    quote_char = '"'
    native_dump_family = "postgresql"

    def get_connection_url(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> str:
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

    def get_list_tables_sql(self) -> str:
        return """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
        """

    def get_table_size_sql(self, table: str) -> str:
        return f"SELECT pg_total_relation_size('\"{table}\"')"

    def get_drop_table_sql(self, table: str, cascade: bool = False) -> str:
        sql = f"DROP TABLE IF EXISTS {self.quote_identifier(table)}"
        if cascade:
            sql += " CASCADE"
        return sql

    def get_truncate_table_sql(self, table: str) -> str:
        return f"TRUNCATE TABLE {self.quote_identifier(table)} CASCADE"

    def get_disable_constraints_sql(self) -> str:
        return "SET session_replication_role = 'replica'"

    def get_enable_constraints_sql(self) -> str:
        return "SET session_replication_role = 'origin'"

    def get_fk_dependencies_sql(self) -> str:
        return """
            SELECT
                tc.table_name,
                ccu.table_name AS referenced_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
        """

    def get_checksum_sql(self, table: str) -> str:
        return f"""
            SELECT MD5(string_agg(row_text, ',' ORDER BY row_text))
            FROM (
                SELECT row_to_json(t)::text AS row_text
                FROM {self.quote_identifier(table)} t
            ) subq
        """

    async def get_auto_value(self, conn, table: str) -> Optional[int]:
        sql = """
            SELECT column_name, pg_get_serial_sequence(:table, column_name) as seq_name
            FROM information_schema.columns
            WHERE table_name = :table
              AND table_schema = 'public'
              AND data_type IN ('integer', 'bigint')
              AND column_default LIKE 'nextval%'
        """
        result = await conn.execute(text(sql), {"table": table})
        row = result.fetchone()
        if row and row[1]:
            seq_result = await conn.execute(text(f"SELECT last_value FROM {row[1]}"))
            seq_row = seq_result.fetchone()
            return seq_row[0] if seq_row else None
        return None

    async def save_auto_values(self, conn, tables: Set[str]) -> Dict[str, Any]:
        sequences: Dict[str, Dict[str, Any]] = {}
        sql = """
            SELECT column_name,
                   pg_get_serial_sequence(:table, column_name) as seq_name
            FROM information_schema.columns
            WHERE table_name = :table
              AND table_schema = 'public'
              AND data_type IN ('integer', 'bigint')
              AND column_default LIKE 'nextval%'
        """
        for table in tables:
            result = await conn.execute(text(sql), {"table": table})
            row = result.fetchone()
            if row and row[1]:
                seq_name = row[1]
                seq_result = await conn.execute(text(f"SELECT last_value, is_called FROM {seq_name}"))
                seq_row = seq_result.fetchone()
                if seq_row:
                    sequences[seq_name] = {
                        "last_value": seq_row[0],
                        "is_called": seq_row[1],
                    }
        return sequences

    async def restore_auto_values(self, conn, values: Dict[str, Any]) -> None:
        for seq_name, info in values.items():
            sql = (
                f"SELECT setval('{seq_name}', {info['last_value']}, "
                f"{str(info['is_called']).lower()})"
            )
            await conn.execute(text(sql))

    def get_create_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        table_name = self.quote_identifier(index_def["table_name"])
        columns_sql = self.build_columns_sql(index_def["column_names"])
        index_type = (index_def.get("index_type") or "btree").upper()
        is_unique = "UNIQUE " if index_def.get("is_unique") else ""
        condition = (index_def.get("condition") or "").strip()
        sql = (
            f"CREATE {is_unique}INDEX {self.quote_identifier(index_name)} "
            f"ON {table_name} USING {index_type} ({columns_sql})"
        )
        if condition:
            sql += f" WHERE {condition}"
        return sql

    def get_drop_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        return f"DROP INDEX IF EXISTS {self.quote_identifier(index_name)}"

    def get_existing_indexes_sql(self) -> str:
        return """
            SELECT
                i.relname AS index_name,
                string_agg(a.attname, ',' ORDER BY x.ordinality) AS columns
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, ordinality) ON true
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
            WHERE t.relname = :table_name
            GROUP BY i.relname
        """

    async def collect_dbms_metrics(self, conn) -> Dict[str, Any]:
        metrics = dict(DEFAULT_DBMS_METRICS)
        metrics["table_sizes_mb"] = {}
        metrics["index_sizes_mb"] = {}

        result = await conn.execute(text("""
            SELECT
                CASE WHEN blks_hit + blks_read = 0 THEN 0
                ELSE round(100.0 * blks_hit / (blks_hit + blks_read), 2)
                END as cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database()
        """))
        row = result.fetchone()
        if row:
            metrics["cache_hit_ratio"] = float(row[0] or 0)
            metrics["buffer_pool_hit_ratio"] = float(row[0] or 0)

        result = await conn.execute(text("""
            SELECT count(*)
            FROM pg_stat_activity
            WHERE datname = current_database()
        """))
        row = result.fetchone()
        if row:
            metrics["active_connections"] = int(row[0] or 0)

        result = await conn.execute(text("""
            SELECT count(*)
            FROM pg_locks
            WHERE NOT granted
        """))
        row = result.fetchone()
        if row:
            metrics["lock_waits"] = int(row[0] or 0)

        result = await conn.execute(text("""
            SELECT relname, pg_total_relation_size(relid) / (1024 * 1024) as size_mb
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10
        """))
        for row in result:
            metrics["table_sizes_mb"][row[0]] = float(row[1] or 0)

        result = await conn.execute(text("""
            SELECT pg_database_size(current_database()) / (1024 * 1024) as size_mb
        """))
        row = result.fetchone()
        if row:
            metrics["total_db_size_mb"] = float(row[0] or 0)

        return metrics

    async def terminate_other_connections(self, conn, db_name: Optional[str]) -> int:
        result = await conn.execute(text("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
              AND state != 'idle'
        """))
        return sum(1 for row in result if row[0])
