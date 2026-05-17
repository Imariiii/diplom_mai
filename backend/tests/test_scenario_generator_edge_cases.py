"""
Расширенные регрессионные тесты schema-aware генерации сценариев.
"""
from backend.database.query_templates import QUERY_TEMPLATES_BY_ID
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.database.scenario_generator import ScenarioGenerator
from backend.database.schema_analyzer import (
    ColumnInfo,
    ForeignKeyInfo,
    SchemaAnalyzer,
    SchemaMetadata,
    TableInfo,
)


def col(
    name,
    category,
    *,
    data_type=None,
    nullable=False,
    pk=False,
    unique=False,
    default=None,
    default_kind=None,
    auto=False,
    partition=False,
):
    return ColumnInfo(
        name=name,
        data_type=data_type or category,
        is_nullable=nullable,
        is_primary_key=pk,
        is_unique=unique,
        is_partition_key=partition,
        is_auto_generated=auto,
        column_default=default,
        has_server_default=default is not None or default_kind is not None,
        default_kind=default_kind,
        category=category,
    )


def fk(from_table, from_column, to_table, to_column="id"):
    return ForeignKeyInfo(
        constraint_name=f"fk_{from_table}_{from_column}",
        from_table=from_table,
        from_column=from_column,
        to_table=to_table,
        to_column=to_column,
    )


def table(name, columns, *, pk=None, row_count=100, fks=None, unique_constraints=None, checks=None):
    info = TableInfo(
        name=name,
        columns=columns,
        primary_key=pk or [],
        row_count=row_count,
        foreign_keys_out=fks or [],
        unique_constraints=unique_constraints or [],
        check_constraints=checks or [],
    )
    for column in info.columns:
        if column.name in info.primary_key:
            column.is_primary_key = True
    for unique_columns in info.unique_constraints:
        if len(unique_columns) == 1:
            info.unique_columns.add(unique_columns[0])
            unique_column = info.get_column(unique_columns[0])
            if unique_column:
                unique_column.is_unique = True
    return info


def metadata(*tables, dbms_type="postgresql"):
    table_map = {item.name: item for item in tables}
    for item in tables:
        for relation in item.foreign_keys_out:
            target = table_map.get(relation.to_table)
            if target:
                target.foreign_keys_in.append(relation)
    analyzer = SchemaAnalyzer.__new__(SchemaAnalyzer)
    for item in tables:
        item.capabilities = analyzer._classify_table(item, table_map)
    return SchemaMetadata(
        connection_id="test",
        connection_name="synthetic",
        dbms_type=dbms_type,
        tables=table_map,
    )


def insert_query(generator, schema, table_name):
    return generator._template_insert_basic(
        metadata=schema,
        table=schema.tables[table_name],
        template=QUERY_TEMPLATES_BY_ID["insert_basic"],
    )


class TestScenarioGeneratorEdgeCases:
    def test_ecommerce_insert_uses_parent_fk_samples_and_skips_defaults(self):
        customers = table(
            "customers",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("email", "string", unique=True),
            ],
            pk=["id"],
        )
        orders = table(
            "orders",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("customer_id", "integer"),
                col("status", "string", default="'new'", default_kind="default"),
                col("created_at", "date", default="CURRENT_TIMESTAMP", default_kind="default"),
                col("total_amount", "numeric"),
            ],
            pk=["id"],
            fks=[fk("orders", "customer_id", "customers")],
        )
        schema = metadata(customers, orders)

        query = insert_query(ScenarioGenerator(), schema, "orders")

        assert query is not None
        assert query["sql_template"] == (
            "INSERT INTO orders (customer_id, total_amount) "
            "VALUES ({insert_customer_id}, {insert_total_amount})"
        )
        assert {
            (param["param_name"], param["table_ref"], param["column_ref"])
            for param in query["params"]
        } == {
            ("insert_customer_id", "customers", "id"),
            ("insert_total_amount", "orders", "total_amount"),
        }

    def test_heuristic_fk_mapping_handles_missing_constraints_for_id_columns(self):
        organization = table(
            "organization",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("name", "string"),
            ],
            pk=["id"],
        )
        employee = table(
            "employee",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("organization_id", "integer"),
                col("full_name", "string"),
            ],
            pk=["id"],
        )
        schema = metadata(organization, employee)

        query = insert_query(ScenarioGenerator(), schema, "employee")

        assert query is not None
        assert {
            (param["param_name"], param["table_ref"], param["column_ref"])
            for param in query["params"]
        } == {
            ("insert_organization_id", "organization", "id"),
            ("insert_full_name", "employee", "full_name"),
        }

    def test_insert_skips_unsupported_required_json_payload(self):
        events = table(
            "events",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("payload", "other", data_type="jsonb"),
            ],
            pk=["id"],
        )
        schema = metadata(events)

        query = insert_query(ScenarioGenerator(), schema, "events")

        assert query is None
        assert "insert_safe" not in schema.tables["events"].capabilities

    def test_insert_allows_nullable_unsupported_payload_by_omitting_it(self):
        events = table(
            "events",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("payload", "other", data_type="jsonb", nullable=True),
                col("event_type", "string"),
            ],
            pk=["id"],
        )
        schema = metadata(events)

        query = insert_query(ScenarioGenerator(), schema, "events")

        assert query is not None
        assert query["sql_template"] == "INSERT INTO events (event_type) VALUES ('{insert_event_type}')"

    def test_boolean_required_column_uses_literal_true_without_param(self):
        flags = table(
            "feature_flags",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("is_enabled", "boolean"),
                col("name", "string"),
            ],
            pk=["id"],
        )
        schema = metadata(flags)

        query = insert_query(ScenarioGenerator(), schema, "feature_flags")

        assert query is not None
        assert "is_enabled, name" in query["sql_template"]
        assert "TRUE" in query["sql_template"]
        assert {param["param_name"] for param in query["params"]} == {"insert_name"}

    def test_composite_primary_key_table_is_not_read_update_delete_candidate(self):
        order_items = table(
            "order_items",
            [
                col("order_id", "integer", pk=True),
                col("line_no", "integer", pk=True),
                col("quantity", "integer"),
            ],
            pk=["order_id", "line_no"],
            row_count=1000,
        )
        schema = metadata(order_items)
        generator = ScenarioGenerator()

        assert generator._template_select_by_pk(
            schema,
            order_items,
            QUERY_TEMPLATES_BY_ID["select_by_pk"],
        ) is None
        assert generator._template_update_numeric_by_pk(
            schema,
            order_items,
            QUERY_TEMPLATES_BY_ID["update_numeric_by_pk"],
        ) is None
        assert generator._template_delete_by_pk(
            schema,
            order_items,
            QUERY_TEMPLATES_BY_ID["delete_by_pk"],
        ) is None

    def test_update_numeric_skips_heuristic_foreign_key_column(self):
        tenant = table(
            "tenant",
            [col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity")],
            pk=["id"],
        )
        account = table(
            "account",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("tenant_id", "integer"),
                col("balance", "numeric"),
            ],
            pk=["id"],
        )
        schema = metadata(tenant, account)

        query = ScenarioGenerator()._template_update_numeric_by_pk(
            schema,
            account,
            QUERY_TEMPLATES_BY_ID["update_numeric_by_pk"],
        )

        assert query is not None
        assert "SET balance = balance + 1" in query["sql_template"]
        assert "tenant_id" not in query["sql_template"]

    def test_delete_safe_only_for_leaf_tables(self):
        parent = table(
            "parent",
            [col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity")],
            pk=["id"],
        )
        child = table(
            "child",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("parent_id", "integer"),
            ],
            pk=["id"],
            fks=[fk("child", "parent_id", "parent")],
        )
        schema = metadata(parent, child)

        assert "delete_safe" not in schema.tables["parent"].capabilities
        assert "delete_safe" in schema.tables["child"].capabilities

    def test_sync_foreign_keys_in_populates_incoming_references(self):
        parent = table(
            "parent",
            [col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity")],
            pk=["id"],
        )
        child = table(
            "child",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("parent_id", "integer"),
            ],
            pk=["id"],
            fks=[fk("child", "parent_id", "parent")],
        )
        table_map = {parent.name: parent, child.name: child}

        SchemaAnalyzer.sync_foreign_keys_in(table_map)

        assert len(parent.foreign_keys_in) == 1
        assert parent.foreign_keys_in[0].from_table == "child"
        assert child.foreign_keys_in == []

    def test_common_metadata_merge_parent_not_delete_safe(self):
        customers = table(
            "olist_customers_dataset",
            [col("customer_id", "string", pk=True)],
            pk=["customer_id"],
            row_count=1000,
        )
        orders = table(
            "olist_orders_dataset",
            [
                col("order_id", "string", pk=True),
                col("customer_id", "string"),
            ],
            pk=["order_id"],
            row_count=5000,
            fks=[fk("olist_orders_dataset", "customer_id", "olist_customers_dataset", "customer_id")],
        )
        reference = metadata(customers, orders)

        common = ScenarioGenerator()._build_common_capability_metadata(
            reference_metadata=reference,
            all_metadata=[reference, reference],
        )

        assert common.tables["olist_customers_dataset"].foreign_keys_in
        assert "delete_safe" not in common.tables["olist_customers_dataset"].capabilities
        assert "delete_safe" in common.tables["olist_orders_dataset"].capabilities

    def test_delete_template_includes_not_exists_when_referenced(self):
        parent = table(
            "parent",
            [col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity")],
            pk=["id"],
        )
        child = table(
            "child",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("parent_id", "integer"),
            ],
            pk=["id"],
            fks=[fk("child", "parent_id", "parent")],
        )
        schema = metadata(parent, child)
        generator = ScenarioGenerator()

        query = generator._template_delete_by_pk(
            schema,
            schema.tables["parent"],
            QUERY_TEMPLATES_BY_ID["delete_by_pk"],
        )

        assert query is not None
        assert "NOT EXISTS" in query["sql_template"]
        assert "FROM child ref" in query["sql_template"]
        assert "никто не ссылается" in query["description"]

        leaf_query = generator._template_delete_by_pk(
            schema,
            schema.tables["child"],
            QUERY_TEMPLATES_BY_ID["delete_by_pk"],
        )
        assert leaf_query is not None
        assert "NOT EXISTS" not in leaf_query["sql_template"]

    def test_mixed_scenario_still_contains_select_update_insert_when_safe(self):
        customer = table(
            "customer",
            [col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity")],
            pk=["id"],
            row_count=200,
        )
        payment = table(
            "payment",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("customer_id", "integer"),
                col("amount", "numeric"),
                col("paid_at", "date"),
            ],
            pk=["id"],
            row_count=500,
            fks=[fk("payment", "customer_id", "customer")],
        )
        schema = metadata(customer, payment)

        queries, _ = ScenarioGenerator()._build_scenario_assets(schema, "mixed_light")

        assert {"select", "update", "insert"}.issubset({query["query_type"] for query in queries})
        insert_sql = next(query["sql_template"] for query in queries if query["query_type"] == "insert")
        assert insert_sql == (
            "INSERT INTO payment (customer_id, amount, paid_at) "
            "VALUES ({insert_customer_id}, {insert_amount}, '{insert_paid_at}')"
        )

    def test_preflight_accepts_defaulted_required_column_omitted_from_insert(self):
        audit = table(
            "audit_log",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("message", "string"),
                col("created_at", "date", default="CURRENT_TIMESTAMP", default_kind="default"),
            ],
            pk=["id"],
        )
        schema = metadata(audit)
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO audit_log (message) VALUES ('{insert_message}')",
            schema,
            "Audit DB",
            errors,
            warnings,
        )

        assert errors == []

    def test_preflight_detects_column_value_count_mismatch(self):
        audit = table(
            "audit_log",
            [
                col("id", "integer", pk=True, auto=True, default="identity", default_kind="identity"),
                col("message", "string"),
            ],
            pk=["id"],
        )
        schema = metadata(audit)
        validator = ScenarioBundleValidator.__new__(ScenarioBundleValidator)
        errors = []
        warnings = []

        validator._validate_write_query(
            "INSERT INTO audit_log (message) VALUES ('{insert_message}', TRUE)",
            schema,
            "Audit DB",
            errors,
            warnings,
        )

        assert "Audit DB: INSERT в audit_log имеет разное число колонок и значений" in errors

    def test_normalize_legacy_column_row_marks_default_from_six_column_dialect_row(self):
        row = ("orders", "created_at", "timestamp", "NO", "CURRENT_TIMESTAMP", 4)

        normalized = SchemaAnalyzer._normalize_column_row(row)

        assert normalized[0] == "orders"
        assert normalized[4] == "CURRENT_TIMESTAMP"
        assert normalized[8] is True

    def test_normalize_column_row_treats_default_null_as_no_default(self):
        row = ("orders", "comment", "text", "YES", "NULL", 5, None, "default", True)

        normalized = SchemaAnalyzer._normalize_column_row(row)

        assert normalized[4] is None
        assert normalized[7] is None
        assert normalized[8] is False

    def test_auto_generated_detection_distinguishes_mysql_on_update_from_generated_column(self):
        analyzer = SchemaAnalyzer.__new__(SchemaAnalyzer)

        assert analyzer._is_auto_generated(
            "current_timestamp() on update current_timestamp()",
            default_kind="default",
        ) is False
        assert analyzer._is_auto_generated(None, default_kind="generated") is True
        assert analyzer._is_auto_generated(None, identity_generation="ALWAYS") is True
