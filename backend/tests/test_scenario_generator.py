"""
Тесты генератора сценариев нагрузочного тестирования.
"""
from backend.database.query_templates import QUERY_TEMPLATES_BY_ID
from backend.database.scenario_generator import ScenarioGenerator
from backend.database.schema_analyzer import ColumnInfo, SchemaMetadata, TableInfo


class TestScenarioGenerator:
    def test_update_timestamp_uses_existing_table_value(self):
        table = TableInfo(
            name="payment",
            row_count=100,
            primary_key=["payment_id"],
            columns=[
                ColumnInfo(
                    name="payment_id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    category="integer",
                ),
                ColumnInfo(
                    name="payment_date",
                    data_type="timestamp with time zone",
                    is_nullable=False,
                    category="date",
                ),
                ColumnInfo(
                    name="last_update",
                    data_type="timestamp with time zone",
                    is_nullable=False,
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_update_timestamp_by_pk(
            metadata=None,
            table=table,
            template=QUERY_TEMPLATES_BY_ID["update_timestamp_by_pk"],
        )

        assert query is not None
        assert "CURRENT_TIMESTAMP" not in query["sql_template"]
        assert query["sql_template"] == (
            "UPDATE payment SET last_update = '{payment_last_update}' "
            "WHERE payment_id = {payment_payment_id}"
        )
        assert query["params"] == [
            {
                "param_name": "payment_payment_id",
                "param_type": "random_from_table",
                "table_ref": "payment",
                "column_ref": "payment_id",
            },
            {
                "param_name": "payment_last_update",
                "param_type": "random_from_table",
                "table_ref": "payment",
                "column_ref": "last_update",
            },
        ]

    def test_update_timestamp_skips_business_date_without_update_column(self):
        table = TableInfo(
            name="olist_orders_dataset",
            row_count=100,
            primary_key=["order_id"],
            columns=[
                ColumnInfo(
                    name="order_id",
                    data_type="varchar",
                    is_nullable=False,
                    is_primary_key=True,
                    category="string",
                ),
                ColumnInfo(
                    name="order_purchase_timestamp",
                    data_type="timestamp",
                    is_nullable=False,
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_update_timestamp_by_pk(
            metadata=None,
            table=table,
            template=QUERY_TEMPLATES_BY_ID["update_timestamp_by_pk"],
        )

        assert query is None

    def test_update_numeric_skips_partition_key(self):
        table = TableInfo(
            name="events",
            row_count=100,
            primary_key=["id"],
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    category="integer",
                ),
                ColumnInfo(
                    name="tenant_id",
                    data_type="integer",
                    is_nullable=False,
                    is_partition_key=True,
                    category="integer",
                ),
            ],
        )

        query = ScenarioGenerator()._template_update_numeric_by_pk(
            metadata=None,
            table=table,
            template=QUERY_TEMPLATES_BY_ID["update_numeric_by_pk"],
        )

        assert query is None

    def test_insert_date_uses_existing_table_values(self):
        table = TableInfo(
            name="payment",
            row_count=100,
            primary_key=["payment_id"],
            columns=[
                ColumnInfo(
                    name="payment_id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    category="integer",
                ),
                ColumnInfo(
                    name="payment_date",
                    data_type="timestamp",
                    is_nullable=False,
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="postgresql",
                tables={"payment": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is not None
        assert query["sql_template"] == (
            "INSERT INTO payment (payment_date) VALUES ('{insert_payment_date}')"
        )
        assert query["params"] == [
            {
                "param_name": "insert_payment_date",
                "param_type": "random_from_table",
                "table_ref": "payment",
                "column_ref": "payment_date",
            }
        ]

    def test_insert_uses_existing_values_for_non_unique_scalars(self):
        table = TableInfo(
            name="olist_geolocation_dataset",
            row_count=100,
            columns=[
                ColumnInfo(
                    name="geolocation_zip_code_prefix",
                    data_type="int",
                    is_nullable=False,
                    category="integer",
                ),
                ColumnInfo(
                    name="geolocation_lat",
                    data_type="double",
                    is_nullable=False,
                    category="numeric",
                ),
                ColumnInfo(
                    name="geolocation_lng",
                    data_type="double",
                    is_nullable=False,
                    category="numeric",
                ),
                ColumnInfo(
                    name="geolocation_city",
                    data_type="varchar",
                    is_nullable=False,
                    category="string",
                ),
                ColumnInfo(
                    name="geolocation_state",
                    data_type="varchar",
                    is_nullable=False,
                    category="string",
                ),
            ],
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="mysql",
                tables={"olist_geolocation_dataset": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is not None
        assert all(param["param_type"] == "random_from_table" for param in query["params"])
        assert {
            (param["param_name"], param["table_ref"], param["column_ref"])
            for param in query["params"]
        } == {
            (
                "insert_geolocation_zip_code_prefix",
                "olist_geolocation_dataset",
                "geolocation_zip_code_prefix",
            ),
            ("insert_geolocation_lat", "olist_geolocation_dataset", "geolocation_lat"),
            ("insert_geolocation_lng", "olist_geolocation_dataset", "geolocation_lng"),
            ("insert_geolocation_city", "olist_geolocation_dataset", "geolocation_city"),
            ("insert_geolocation_state", "olist_geolocation_dataset", "geolocation_state"),
        }

    def test_insert_skips_primary_key_with_server_default(self):
        table = TableInfo(
            name="rental",
            row_count=100,
            primary_key=["rental_id"],
            columns=[
                ColumnInfo(
                    name="rental_id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    column_default="nextval('rental_rental_id_seq'::regclass)",
                    has_server_default=True,
                    default_kind="serial",
                    category="integer",
                ),
                ColumnInfo(
                    name="rental_date",
                    data_type="timestamp",
                    is_nullable=False,
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="postgresql",
                tables={"rental": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is not None
        assert "rental_id" not in query["sql_template"]

    def test_insert_skips_table_when_required_primary_key_has_no_default(self):
        table = TableInfo(
            name="rental",
            row_count=100,
            primary_key=["rental_id"],
            columns=[
                ColumnInfo(
                    name="rental_id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    category="integer",
                ),
                ColumnInfo(
                    name="rental_date",
                    data_type="timestamp",
                    is_nullable=False,
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="postgresql",
                tables={"rental": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is None

    def test_insert_skips_table_with_composite_unique_constraint(self):
        table = TableInfo(
            name="rental",
            row_count=100,
            primary_key=["rental_id"],
            unique_constraints=[["rental_date", "inventory_id", "customer_id"]],
            columns=[
                ColumnInfo(
                    name="rental_id",
                    data_type="integer",
                    is_nullable=False,
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
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="postgresql",
                tables={"rental": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is None

    def test_insert_omits_non_pk_column_with_server_default(self):
        table = TableInfo(
            name="payment",
            row_count=100,
            primary_key=["payment_id"],
            columns=[
                ColumnInfo(
                    name="payment_id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    column_default="auto_increment",
                    has_server_default=True,
                    default_kind="auto_increment",
                    category="integer",
                ),
                ColumnInfo("amount", "decimal", False, category="numeric"),
                ColumnInfo(
                    name="last_update",
                    data_type="timestamp",
                    is_nullable=False,
                    column_default="current_timestamp() on update current_timestamp()",
                    has_server_default=True,
                    default_kind="default",
                    category="date",
                ),
            ],
        )

        query = ScenarioGenerator()._template_insert_basic(
            metadata=SchemaMetadata(
                connection_id="test",
                connection_name="test",
                dbms_type="mysql",
                tables={"payment": table},
            ),
            table=table,
            template=QUERY_TEMPLATES_BY_ID["insert_basic"],
        )

        assert query is not None
        assert "last_update" not in query["sql_template"]
