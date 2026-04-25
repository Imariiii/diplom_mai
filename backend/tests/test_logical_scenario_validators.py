"""
Тесты валидаторов logical database и scenario bundle.
"""
from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.database.schema_analyzer import ColumnInfo, SchemaMetadata, TableInfo


def _table(name, columns, primary_key=None, row_count=100, foreign_keys_out=None):
    return TableInfo(
        name=name,
        columns=columns,
        primary_key=primary_key or [],
        row_count=row_count,
        foreign_keys_out=foreign_keys_out or [],
    )


def _metadata(connection_id, tables):
    return SchemaMetadata(
        connection_id=connection_id,
        connection_name=connection_id,
        dbms_type="postgresql",
        tables={table.name: table for table in tables},
    )


class TestLogicalDatabaseValidator:
    def test_compare_metadata_reports_missing_column_as_error(self):
        reference = _metadata("ref", [
            _table(
                "payment",
                [
                    ColumnInfo("payment_id", "integer", False, is_primary_key=True, category="integer"),
                    ColumnInfo("amount", "numeric", False, category="numeric"),
                ],
                primary_key=["payment_id"],
            )
        ])
        target = _metadata("target", [
            _table(
                "payment",
                [
                    ColumnInfo("payment_id", "integer", False, is_primary_key=True, category="integer"),
                ],
                primary_key=["payment_id"],
            )
        ])
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target DB", errors, warnings)

        assert "Target DB: в payment отсутствует колонка amount" in errors

    def test_compare_metadata_warns_on_row_count_drift(self):
        reference = _metadata("ref", [
            _table(
                "customer",
                [ColumnInfo("customer_id", "integer", False, is_primary_key=True, category="integer")],
                primary_key=["customer_id"],
                row_count=1000,
            )
        ])
        target = _metadata("target", [
            _table(
                "customer",
                [ColumnInfo("customer_id", "integer", False, is_primary_key=True, category="integer")],
                primary_key=["customer_id"],
                row_count=100,
            )
        ])
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target DB", errors, warnings)

        assert errors == []
        assert any("row_count таблицы customer отличается" in warning for warning in warnings)


class TestScenarioBundleValidator:
    def test_write_query_on_partition_key_is_blocking_error(self):
        metadata = _metadata("pg", [
            _table(
                "payment",
                [
                    ColumnInfo("payment_id", "integer", False, is_primary_key=True, category="integer"),
                    ColumnInfo("payment_date", "timestamp", False, is_partition_key=True, category="date"),
                ],
                primary_key=["payment_id"],
            )
        ])
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "UPDATE payment SET payment_date = '{payment_payment_date}' WHERE payment_id = {payment_payment_id}",
            metadata,
            "Pagila",
            errors,
            warnings,
        )

        assert "Pagila: UPDATE меняет partition key payment.payment_date" in errors

    def test_extract_table_names_from_generated_sql(self):
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)

        tables = validator._extract_table_names(
            "SELECT a.*, b.* FROM payment a JOIN customer b ON a.customer_id = b.customer_id "
            "WHERE a.payment_id = {payment_payment_id}"
        )

        assert tables == {"payment", "customer"}
