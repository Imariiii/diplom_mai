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
    def test_compare_metadata_reports_missing_column_as_warning(self):
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

        assert errors == []
        assert "Target DB: в payment отсутствует колонка amount" in warnings

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

    def test_insert_missing_required_column_is_blocking_error(self):
        metadata = _metadata("pg", [
            _table(
                "rental",
                [
                    ColumnInfo("rental_id", "integer", False, is_primary_key=True, category="integer"),
                    ColumnInfo("rental_date", "timestamp", False, category="date"),
                ],
                primary_key=["rental_id"],
            )
        ])
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO rental (rental_date) VALUES ('{insert_rental_date}')",
            metadata,
            "Pagila",
            errors,
            warnings,
        )

        assert "Pagila: INSERT в rental пропускает обязательную колонку rental_id без server default" in errors

    def test_insert_auto_generated_column_is_blocking_error(self):
        metadata = _metadata("pg", [
            _table(
                "rental",
                [
                    ColumnInfo(
                        "rental_id",
                        "integer",
                        False,
                        is_primary_key=True,
                        is_auto_generated=True,
                        column_default="nextval('rental_rental_id_seq'::regclass)",
                        has_server_default=True,
                        default_kind="serial",
                        category="integer",
                    ),
                    ColumnInfo("rental_date", "timestamp", False, category="date"),
                ],
                primary_key=["rental_id"],
            )
        ])
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO rental (rental_id, rental_date) VALUES ({insert_rental_id}, '{insert_rental_date}')",
            metadata,
            "Pagila",
            errors,
            warnings,
        )

        assert "Pagila: INSERT в rental явно заполняет auto-generated колонку rental_id" in errors

    def test_insert_composite_unique_is_blocking_error(self):
        metadata = _metadata("pg", [
            _table(
                "rental",
                [
                    ColumnInfo(
                        "rental_id",
                        "integer",
                        False,
                        is_primary_key=True,
                        is_auto_generated=True,
                        column_default="nextval('rental_rental_id_seq'::regclass)",
                        has_server_default=True,
                        default_kind="serial",
                        category="integer",
                    ),
                    ColumnInfo("rental_date", "timestamp", False, category="date"),
                    ColumnInfo("inventory_id", "integer", False, category="integer"),
                    ColumnInfo("customer_id", "integer", False, category="integer"),
                ],
                primary_key=["rental_id"],
            )
        ])
        metadata.tables["rental"].unique_constraints.append(["rental_date", "inventory_id", "customer_id"])
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO rental (rental_date, inventory_id, customer_id) "
            "VALUES ('{insert_rental_date}', {insert_inventory_id}, {insert_customer_id})",
            metadata,
            "Pagila",
            errors,
            warnings,
        )

        assert any("composite UNIQUE (rental_date, inventory_id, customer_id)" in error for error in errors)

    def test_insert_with_now_function_matches_column_count(self):
        metadata = _metadata("pg", [
            _table(
                "rental",
                [
                    ColumnInfo(
                        "rental_id",
                        "integer",
                        False,
                        is_primary_key=True,
                        is_auto_generated=True,
                        column_default="nextval('rental_rental_id_seq'::regclass)",
                        has_server_default=True,
                        default_kind="serial",
                        category="integer",
                    ),
                    ColumnInfo("rental_date", "timestamp", False, category="date"),
                    ColumnInfo("inventory_id", "smallint", False, category="integer"),
                    ColumnInfo("customer_id", "smallint", False, category="integer"),
                    ColumnInfo("staff_id", "smallint", False, category="integer"),
                ],
                primary_key=["rental_id"],
            )
        ])
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id) "
            "VALUES (NOW(), {inventory_id}, {customer_id}, {staff_id})",
            metadata,
            "Pagila",
            errors,
            warnings,
        )

        assert not any("разное число колонок и значений" in error for error in errors)
