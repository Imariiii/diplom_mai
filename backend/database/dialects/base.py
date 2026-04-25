"""
Базовая абстракция диалекта СУБД для централизованной DBMS-специфичной логики.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text


DEFAULT_DBMS_METRICS: Dict[str, Any] = {
    "cache_hit_ratio": 0,
    "buffer_pool_hit_ratio": 0,
    "lock_waits": 0,
    "deadlocks": 0,
    "active_connections": 0,
    "table_sizes_mb": {},
    "index_sizes_mb": {},
    "total_db_size_mb": 0,
}


class DbmsDialect(ABC):
    """Базовый класс диалекта СУБД."""

    name: str = ""
    display_name: str = ""
    default_port: int = 0
    quote_char: str = '"'
    native_dump_family: str = ""

    def quote_identifier(self, identifier: str) -> str:
        """Безопасно обрамить идентификатор символом кавычки текущей СУБД."""
        sanitized = identifier.strip().replace(self.quote_char, "")
        return f"{self.quote_char}{sanitized}{self.quote_char}"

    def split_columns(self, column_names: str) -> List[str]:
        """Нормализовать строку со списком колонок."""
        return [column.strip() for column in column_names.split(",") if column.strip()]

    def build_columns_sql(self, column_names: str) -> str:
        """Собрать SQL-список колонок с корректным quoting."""
        return ", ".join(self.quote_identifier(column) for column in self.split_columns(column_names))

    @abstractmethod
    def get_connection_url(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> str:
        """Построить SQLAlchemy URL подключения."""

    @abstractmethod
    def get_list_tables_sql(self) -> str:
        """SQL для получения списка BASE TABLE текущей базы."""

    @abstractmethod
    def get_columns_sql(self) -> str:
        """SQL для чтения колонок таблиц текущей базы."""

    @abstractmethod
    def get_primary_keys_sql(self) -> str:
        """SQL для чтения primary key таблиц текущей базы."""

    @abstractmethod
    def get_foreign_keys_detailed_sql(self) -> str:
        """SQL для чтения детальной информации о foreign key."""

    @abstractmethod
    def get_unique_constraints_sql(self) -> str:
        """SQL для чтения уникальных ограничений таблиц."""

    def get_row_count_sql(self, table: str) -> str:
        """SQL для подсчёта строк в таблице."""
        return f"SELECT COUNT(*) FROM {self.quote_identifier(table)}"

    def get_partition_columns_sql(self) -> Optional[str]:
        """SQL для чтения колонок партиционирования, если СУБД это поддерживает."""
        return None

    def get_sample_column_values_sql(self, table: str, column: str) -> str:
        """SQL для ограниченной выборки значений колонки."""
        quoted_column = self.quote_identifier(column)
        return (
            f"SELECT {quoted_column} FROM {self.quote_identifier(table)} "
            f"WHERE {quoted_column} IS NOT NULL LIMIT :limit"
        )

    @abstractmethod
    def get_table_size_sql(self, table: str) -> str:
        """SQL для получения размера таблицы в байтах."""

    def get_drop_table_sql(self, table: str, cascade: bool = False) -> str:
        """SQL для удаления таблицы."""
        return f"DROP TABLE IF EXISTS {self.quote_identifier(table)}"

    def get_create_backup_table_sql(self, source_table: str, backup_table: str) -> str:
        """SQL для создания backup-таблицы."""
        return (
            f"CREATE TABLE {self.quote_identifier(backup_table)} "
            f"AS SELECT * FROM {self.quote_identifier(source_table)}"
        )

    def get_truncate_table_sql(self, table: str) -> str:
        """SQL для очистки таблицы перед восстановлением."""
        return f"TRUNCATE TABLE {self.quote_identifier(table)}"

    def get_insert_from_backup_sql(self, table: str, backup_table: str) -> str:
        """SQL для копирования данных из backup-таблицы."""
        return (
            f"INSERT INTO {self.quote_identifier(table)} "
            f"SELECT * FROM {self.quote_identifier(backup_table)}"
        )

    @abstractmethod
    def get_disable_constraints_sql(self) -> str:
        """SQL для временного отключения проверок FK."""

    @abstractmethod
    def get_enable_constraints_sql(self) -> str:
        """SQL для обратного включения проверок FK."""

    def get_disable_strict_mode_sql(self) -> Optional[str]:
        """SQL для отключения strict sql_mode (MySQL/MariaDB). None = не требуется."""
        return None

    def get_enable_strict_mode_sql(self) -> Optional[str]:
        """SQL для восстановления strict sql_mode. None = не требуется."""
        return None

    @abstractmethod
    def get_fk_dependencies_sql(self) -> str:
        """SQL для чтения FK-зависимостей таблиц."""

    async def load_fk_dependencies(self, conn, tables: Set[str]) -> Dict[str, Set[str]]:
        """Загрузить зависимости между таблицами по FK."""
        dependencies: Dict[str, Set[str]] = {}
        result = await conn.execute(text(self.get_fk_dependencies_sql()))
        for row in result:
            table, ref_table = row
            if table in tables and ref_table in tables:
                dependencies.setdefault(table, set()).add(ref_table)
        return dependencies

    @abstractmethod
    def get_checksum_sql(self, table: str) -> str:
        """SQL для вычисления checksum таблицы."""

    def extract_checksum_value(self, row: Any) -> str:
        """Извлечь checksum из результата запроса."""
        if not row:
            return ""
        if isinstance(row, (tuple, list)):
            return row[0] or ""
        return row or ""

    @abstractmethod
    async def get_auto_value(self, conn, table: str) -> Optional[int]:
        """Получить sequence/AUTO_INCREMENT-подобное значение таблицы."""

    @abstractmethod
    async def save_auto_values(self, conn, tables: Set[str]) -> Dict[str, Any]:
        """Сохранить sequence/AUTO_INCREMENT-подобные значения для набора таблиц."""

    @abstractmethod
    async def restore_auto_values(self, conn, values: Dict[str, Any]) -> None:
        """Восстановить sequence/AUTO_INCREMENT-подобные значения."""

    @abstractmethod
    def get_create_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        """SQL для создания индекса."""

    @abstractmethod
    def get_drop_index_sql(self, index_def: Dict[str, Any], index_name: str) -> str:
        """SQL для удаления индекса."""

    @abstractmethod
    def get_existing_indexes_sql(self) -> str:
        """SQL для получения существующих индексов таблицы."""

    @abstractmethod
    async def collect_dbms_metrics(self, conn) -> Dict[str, Any]:
        """Собрать внутренние метрики СУБД."""

    @abstractmethod
    async def terminate_other_connections(self, conn, db_name: Optional[str]) -> int:
        """Завершить остальные активные соединения с целевой базой."""
