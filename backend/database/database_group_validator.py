"""
Проверка совместимости подключений внутри database group.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.schema_analyzer import SchemaAnalyzer, SchemaMetadata, TableInfo
from backend.database.check_constraint_utils import (
    is_redundant_not_null_check,
    normalize_check_constraint,
)


class DatabaseGroupValidator:
    """Валидирует, что подключения logical DB совместимы для общего SQL bundle."""

    def __init__(self, connection_repository: ConnectionRepository):
        self.connection_repository = connection_repository
        self.schema_analyzer = SchemaAnalyzer(connection_repo=connection_repository)

    async def validate_connections(
        self,
        connection_ids: List[str],
        reference_connection_id: Optional[str] = None,
        mode: str = "lenient",
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
                "mode": mode,
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
            return self._result(False, errors, warnings, reference, connections, mode=mode)

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
                mode=mode,
            )

        if len(metadata_by_id) > 1:
            self._validate_capability_intersection(
                metadata_by_id=metadata_by_id,
                reference=reference,
                errors=errors,
                warnings=warnings,
                mode=mode,
            )

        result = self._result(not errors, errors, warnings, reference, connections, mode=mode)
        result["schema_fingerprints"] = {
            connection_id: self.schema_fingerprint(metadata)
            for connection_id, metadata in metadata_by_id.items()
        }
        return result

    def _compare_metadata(
        self,
        reference_metadata: SchemaMetadata,
        target_metadata: SchemaMetadata,
        target_name: str,
        errors: List[str],
        warnings: List[str],
        mode: str = "lenient",
    ) -> None:
        reference_tables = reference_metadata.tables
        target_tables = target_metadata.tables

        missing_tables = sorted(set(reference_tables) - set(target_tables))
        extra_tables = sorted(set(target_tables) - set(reference_tables))
        for table_name in missing_tables:
            self._issue(
                errors,
                warnings,
                f"{target_name}: отсутствует таблица {table_name}",
                mode,
                strict_error=True,
            )
        for table_name in extra_tables:
            warnings.append(f"{target_name}: лишняя таблица {table_name}")

        common_tables_count = 0
        for table_name, reference_table in reference_tables.items():
            target_table = target_tables.get(table_name)
            if not target_table:
                continue
            common_tables_count += 1
            self._compare_table(reference_table, target_table, target_name, errors, warnings, mode=mode)

        if common_tables_count == 0:
            errors.append(f"{target_name}: нет пересечения таблиц с эталоном")

    def _compare_table(
        self,
        reference_table: TableInfo,
        target_table: TableInfo,
        target_name: str,
        errors: List[str],
        warnings: List[str],
        mode: str = "lenient",
    ) -> None:
        reference_columns = {column.name: column for column in reference_table.columns}
        target_columns = {column.name: column for column in target_table.columns}

        for column_name, reference_column in reference_columns.items():
            target_column = target_columns.get(column_name)
            if not target_column:
                self._issue(
                    errors,
                    warnings,
                    f"{target_name}: в {reference_table.name} отсутствует колонка {column_name}",
                    mode,
                    strict_error=reference_column.category != "other",
                )
                continue
            if target_column.category != reference_column.category:
                self._issue(
                    errors,
                    warnings,
                    f"{target_name}: {reference_table.name}.{column_name} имеет категорию "
                    f"{target_column.category}, ожидалась {reference_column.category}",
                    mode,
                    strict_error=True,
                )
            if target_column.is_nullable != reference_column.is_nullable:
                self._issue(
                    errors,
                    warnings,
                    f"{target_name}: {reference_table.name}.{column_name} отличается nullable",
                    mode,
                    strict_error=not reference_column.is_nullable,
                )
            if self._insert_default_signature(target_column) != self._insert_default_signature(reference_column):
                self._issue(
                    errors,
                    warnings,
                    f"{target_name}: {reference_table.name}.{column_name} отличается server default/identity",
                    mode,
                    strict_error=self._default_drift_is_blocking(reference_column, target_column),
                )

        if tuple(reference_table.primary_key) != tuple(target_table.primary_key):
            self._issue(
                errors,
                warnings,
                f"{target_name}: primary key таблицы {reference_table.name} отличается "
                f"от эталона",
                mode,
                strict_error=True,
            )

        reference_fk = self._fk_signature(reference_table)
        target_fk = self._fk_signature(target_table)
        if reference_fk != target_fk:
            self._issue(
                errors,
                warnings,
                f"{target_name}: FK-связи таблицы {reference_table.name} отличаются от эталона",
                mode,
                strict_error=False,
            )

        if self._unique_signature(reference_table) != self._unique_signature(target_table):
            self._issue(
                errors,
                warnings,
                f"{target_name}: UNIQUE constraints таблицы {reference_table.name} отличаются от эталона",
                mode,
                strict_error=False,
            )

        if self._check_signature(reference_table) != self._check_signature(target_table):
            self._issue(
                errors,
                warnings,
                f"{target_name}: CHECK constraints таблицы {reference_table.name} отличаются от эталона",
                mode,
                strict_error=True,
            )

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

    def _unique_signature(self, table: TableInfo) -> Tuple[Tuple[str, ...], ...]:
        return tuple(sorted(tuple(columns) for columns in table.unique_constraints))

    def _check_signature(self, table: TableInfo) -> Tuple[str, ...]:
        return tuple(sorted({
            normalized
            for check in table.check_constraints
            for normalized in [normalize_check_constraint(check)]
            if normalized and not is_redundant_not_null_check(normalized)
        }))

    def _insert_default_signature(self, column) -> Tuple[bool, bool, str, str]:
        column_default = self._normalize_default_for_comparison(getattr(column, "column_default", None))
        default_kind = (column.default_kind or "").lower()
        identity_generation = (column.identity_generation or "").lower()
        has_server_default = bool(column.has_server_default or column_default or identity_generation)
        if not column_default and default_kind == "default" and not identity_generation:
            default_kind = ""
            has_server_default = False
        if column.is_primary_key and self._is_generated_key_default(
            column_default=column_default,
            default_kind=default_kind,
            identity_generation=identity_generation,
            is_auto_generated=bool(column.is_auto_generated),
        ):
            return (True, True, "generated_key", "")
        return (
            has_server_default,
            bool(column.is_auto_generated),
            default_kind,
            identity_generation,
        )

    @staticmethod
    def _is_generated_key_default(
        column_default: Optional[str],
        default_kind: str,
        identity_generation: str,
        is_auto_generated: bool,
    ) -> bool:
        default = (column_default or "").lower()
        return (
            is_auto_generated
            or "nextval(" in default
            or "auto_increment" in default
            or default_kind in {"serial", "identity", "auto_increment", "generated"}
            or bool(identity_generation)
        )

    def _default_drift_is_blocking(self, reference_column, target_column) -> bool:
        """Определить, опасно ли различие server default для общего bundle."""
        if reference_column.is_primary_key and target_column.is_primary_key:
            # Если в одной СУБД PK заполняется AUTO_INCREMENT/sequence, а в другой требует явного
            # значения, common metadata отключит автозаполнение и INSERT для такой таблицы не будет
            # построен без явного безопасного плана. Это drift, но не несовместимость схемы.
            return False
        return not reference_column.is_nullable

    @staticmethod
    def _normalize_default_for_comparison(column_default) -> Optional[str]:
        if column_default is None:
            return None
        normalized = str(column_default).strip()
        if not normalized or normalized.lower() == "null":
            return None
        return normalized

    def _validate_capability_intersection(
        self,
        metadata_by_id: Dict[str, SchemaMetadata],
        reference,
        errors: List[str],
        warnings: List[str],
        mode: str,
    ) -> None:
        capability_sets: List[Set[str]] = []
        table_sets: List[Set[str]] = []
        for metadata in metadata_by_id.values():
            table_sets.append(set(metadata.tables.keys()))
            capability_sets.append({
                capability
                for table in metadata.tables.values()
                for capability in table.capabilities
            })
        if table_sets and not set.intersection(*table_sets):
            errors.append("У выбранных подключений нет общего набора таблиц для database group")
        if capability_sets and not set.intersection(*capability_sets):
            self._issue(
                errors,
                warnings,
                "У выбранных подключений нет общего набора возможностей для генерации сценариев",
                mode,
                strict_error=True,
            )

    @staticmethod
    def _issue(errors: List[str], warnings: List[str], message: str, mode: str, strict_error: bool) -> None:
        if mode == "strict" and strict_error:
            errors.append(message)
        else:
            warnings.append(message)

    def schema_fingerprint(self, metadata: SchemaMetadata) -> Dict[str, Any]:
        """Построить компактный fingerprint схемы для drift detection."""
        return {
            "dbms_type": metadata.dbms_type,
            "tables": {
                table_name: {
                    "columns": {
                        column.name: {
                            "category": column.category,
                            "nullable": column.is_nullable,
                            "primary_key": column.is_primary_key,
                            "unique": column.is_unique,
                            "auto_generated": column.is_auto_generated,
                            "default": self._insert_default_signature(column),
                        }
                        for column in table.columns
                    },
                    "primary_key": list(table.primary_key),
                    "foreign_keys": self._fk_signature(table),
                    "unique": self._unique_signature(table),
                    "checks": self._check_signature(table),
                    "capabilities": sorted(table.capabilities),
                }
                for table_name, table in sorted(metadata.tables.items())
            },
        }

    def _result(self, valid, errors, warnings, reference, connections, mode: str = "lenient") -> Dict[str, Any]:
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "reference_connection_id": str(reference.id) if reference else None,
            "reference_connection_name": reference.name if reference else None,
            "mode": mode,
            "connections": [
                {"id": str(connection.id), "name": connection.name, "dbms_type": connection.dbms_type}
                for connection in connections
            ],
        }
