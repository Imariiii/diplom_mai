"""
Проверка совместимости подключений внутри logical database.
"""
from typing import Any, Dict, List, Optional, Tuple

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.schema_analyzer import SchemaAnalyzer, SchemaMetadata, TableInfo


class LogicalDatabaseValidator:
    """Валидирует, что подключения logical DB совместимы для общего SQL bundle."""

    def __init__(self, connection_repository: ConnectionRepository):
        self.connection_repository = connection_repository
        self.schema_analyzer = SchemaAnalyzer(connection_repo=connection_repository)

    async def validate_connections(
        self,
        connection_ids: List[str],
        reference_connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Проверить совместимость набора подключений."""
        connections = await self.connection_repository.bulk_get_connections(connection_ids)
        if len(connections) != len(connection_ids):
            return {
                "valid": False,
                "errors": ["Не удалось загрузить все выбранные подключения"],
                "warnings": [],
                "reference_connection_id": reference_connection_id,
                "connections": [],
            }

        reference = None
        if reference_connection_id:
            reference = next(
                (connection for connection in connections if str(connection.id) == reference_connection_id),
                None,
            )
        if reference is None:
            reference = sorted(connections, key=lambda item: item.name)[0]

        metadata_by_id: Dict[str, SchemaMetadata] = {}
        errors: List[str] = []
        warnings: List[str] = []

        for connection in connections:
            try:
                metadata_by_id[str(connection.id)] = await self.schema_analyzer.analyze_connection(str(connection.id))
            except Exception as exc:
                errors.append(f"{connection.name}: не удалось проанализировать схему: {exc}")

        reference_metadata = metadata_by_id.get(str(reference.id))
        if not reference_metadata:
            errors.append(f"{reference.name}: не удалось получить эталонную схему")
            return self._result(False, errors, warnings, reference, connections)

        for connection in connections:
            metadata = metadata_by_id.get(str(connection.id))
            if not metadata or str(connection.id) == str(reference.id):
                continue
            self._compare_metadata(
                reference_metadata=reference_metadata,
                target_metadata=metadata,
                target_name=connection.name,
                errors=errors,
                warnings=warnings,
            )

        return self._result(not errors, errors, warnings, reference, connections)

    def _compare_metadata(
        self,
        reference_metadata: SchemaMetadata,
        target_metadata: SchemaMetadata,
        target_name: str,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        reference_tables = reference_metadata.tables
        target_tables = target_metadata.tables

        missing_tables = sorted(set(reference_tables) - set(target_tables))
        extra_tables = sorted(set(target_tables) - set(reference_tables))
        for table_name in missing_tables:
            warnings.append(f"{target_name}: отсутствует таблица {table_name}")
        for table_name in extra_tables:
            warnings.append(f"{target_name}: лишняя таблица {table_name}")

        common_tables_count = 0
        for table_name, reference_table in reference_tables.items():
            target_table = target_tables.get(table_name)
            if not target_table:
                continue
            common_tables_count += 1
            self._compare_table(reference_table, target_table, target_name, errors, warnings)

        if common_tables_count == 0:
            errors.append(f"{target_name}: нет пересечения таблиц с эталоном")

    def _compare_table(
        self,
        reference_table: TableInfo,
        target_table: TableInfo,
        target_name: str,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        reference_columns = {column.name: column for column in reference_table.columns}
        target_columns = {column.name: column for column in target_table.columns}

        for column_name, reference_column in reference_columns.items():
            target_column = target_columns.get(column_name)
            if not target_column:
                warnings.append(f"{target_name}: в {reference_table.name} отсутствует колонка {column_name}")
                continue
            if target_column.category != reference_column.category:
                warnings.append(
                    f"{target_name}: {reference_table.name}.{column_name} имеет категорию "
                    f"{target_column.category}, ожидалась {reference_column.category}"
                )
            if target_column.is_nullable != reference_column.is_nullable:
                warnings.append(
                    f"{target_name}: {reference_table.name}.{column_name} отличается nullable"
                )

        if tuple(reference_table.primary_key) != tuple(target_table.primary_key):
            warnings.append(
                f"{target_name}: primary key таблицы {reference_table.name} отличается "
                f"от эталона"
            )

        reference_fk = self._fk_signature(reference_table)
        target_fk = self._fk_signature(target_table)
        if reference_fk != target_fk:
            warnings.append(f"{target_name}: FK-связи таблицы {reference_table.name} отличаются от эталона")

        if reference_table.row_count > 0:
            ratio = target_table.row_count / float(reference_table.row_count)
            if ratio < 0.8 or ratio > 1.25:
                warnings.append(
                    f"{target_name}: row_count таблицы {reference_table.name} отличается "
                    f"от эталона ({target_table.row_count} vs {reference_table.row_count})"
                )

    def _fk_signature(self, table: TableInfo) -> Tuple[Tuple[str, str, str], ...]:
        return tuple(sorted(
            (fk.from_column, fk.to_table, fk.to_column)
            for fk in table.foreign_keys_out
        ))

    def _result(self, valid, errors, warnings, reference, connections) -> Dict[str, Any]:
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "reference_connection_id": str(reference.id) if reference else None,
            "reference_connection_name": reference.name if reference else None,
            "connections": [
                {"id": str(connection.id), "name": connection.name, "dbms_type": connection.dbms_type}
                for connection in connections
            ],
        }
