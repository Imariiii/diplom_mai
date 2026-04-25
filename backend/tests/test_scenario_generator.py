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
