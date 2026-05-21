"""
Регрессионные тесты новой модели database group/schema profile.
"""
from types import SimpleNamespace

import pytest

from backend.database.database_group_validator import DatabaseGroupValidator
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_generator import ScenarioGenerator
from backend.database.schema_analyzer import ColumnInfo, SchemaAnalyzer, SchemaMetadata, TableInfo


def _connection(
    connection_id,
    name,
    *,
    schema_profile_id=None,
    database_group=None,
    profile_source="inherited",
):
    return SimpleNamespace(
        id=connection_id,
        name=name,
        dbms_type="postgresql",
        schema_profile_id=schema_profile_id,
        schema_profile=SimpleNamespace(name="profile") if schema_profile_id else None,
        profile_source=profile_source,
        database_group_id=database_group.id if database_group else None,
        database_group=database_group,
    )


def _metadata(connection_id, table, dbms_type=None):
    resolved_dbms = dbms_type or connection_id
    if resolved_dbms not in {"mysql", "postgresql", "mariadb"}:
        resolved_dbms = "postgresql"
    return SchemaMetadata(
        connection_id=connection_id,
        connection_name=connection_id,
        dbms_type=resolved_dbms,
        tables={table.name: table},
    )


def _table(name, columns, primary_key=None, capabilities=None):
    table = TableInfo(
        name=name,
        columns=columns,
        primary_key=primary_key or [],
        row_count=100,
        capabilities=capabilities or [],
    )
    for column in table.columns:
        column.is_primary_key = column.name in table.primary_key
    return table


class _ConnectionRepo:
    def __init__(self, connections):
        self.connections = connections

    async def bulk_get_connections(self, connection_ids):
        return [
            connection
            for connection in self.connections
            if str(connection.id) in set(connection_ids)
        ]


class _Bundle:
    id = "bundle-1"
    schema_profile_id = "profile-1"
    scenario_template_id = "mixed_light"
    schema_profile = SimpleNamespace(name="profile")

    def to_dict(self):
        return {
            "id": self.id,
            "name": "bundle",
            "description": None,
            "scenario_type": self.scenario_template_id,
            "scenario_template_id": self.scenario_template_id,
            "scenario_template_name": "Mixed",
            "schema_profile_id": self.schema_profile_id,
            "schema_profile_name": "profile",
            "generation_source": "test",
            "is_builtin": True,
            "queries": [],
            "indexes": [],
        }


class _BundleRepo:
    async def get_bundle_for_profile_template(
        self,
        schema_profile_id,
        scenario_template_id,
        bundle_id=None,
        preferred_name=None,
    ):
        assert schema_profile_id == "profile-1"
        assert scenario_template_id == "mixed_light"
        return _Bundle()

    async def get_bundle(self, bundle_id):
        return _Bundle()


class TestDatabaseGroupValidatorStrictMode:
    def test_strict_mode_promotes_missing_column_to_error(self):
        reference = _metadata("ref", _table(
            "orders",
            [
                ColumnInfo("id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("amount", "numeric", False, category="numeric"),
            ],
            primary_key=["id"],
        ))
        target = _metadata("target", _table(
            "orders",
            [ColumnInfo("id", "integer", False, is_primary_key=True, category="integer")],
            primary_key=["id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target", errors, warnings, mode="strict")

        assert "Target: в orders отсутствует колонка amount" in errors
        assert warnings == []

    def test_strict_mode_blocks_required_default_drift(self):
        reference = _metadata("ref", _table(
            "orders",
            [
                ColumnInfo("id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo(
                    "created_at",
                    "timestamp",
                    False,
                    column_default="CURRENT_TIMESTAMP",
                    has_server_default=True,
                    default_kind="default",
                    category="date",
                ),
            ],
            primary_key=["id"],
        ))
        target = _metadata("target", _table(
            "orders",
            [
                ColumnInfo("id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("created_at", "timestamp", False, category="date"),
            ],
            primary_key=["id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target", errors, warnings, mode="strict")

        assert "Target: orders.created_at отличается server default/identity" in errors

    def test_strict_mode_downgrades_primary_key_default_drift_to_warning(self):
        reference = _metadata("pagila", _table(
            "actor",
            [ColumnInfo("actor_id", "integer", False, is_primary_key=True, category="integer")],
            primary_key=["actor_id"],
        ))
        target = _metadata("sakila", _table(
            "actor",
            [
                ColumnInfo(
                    "actor_id",
                    "integer",
                    False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    has_server_default=True,
                    default_kind="auto_increment",
                    category="integer",
                ),
            ],
            primary_key=["actor_id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Sakila", errors, warnings, mode="strict")

        assert errors == []
        assert "Sakila: actor.actor_id отличается server default/identity" in warnings

    def test_strict_mode_treats_serial_and_auto_increment_as_equivalent_key_generation(self):
        reference = _metadata("postgres", _table(
            "actor",
            [
                ColumnInfo(
                    "actor_id",
                    "integer",
                    False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    column_default="nextval('actor_actor_id_seq'::regclass)",
                    has_server_default=True,
                    default_kind="serial",
                    category="integer",
                ),
            ],
            primary_key=["actor_id"],
        ))
        target = _metadata("mysql", _table(
            "actor",
            [
                ColumnInfo(
                    "actor_id",
                    "integer",
                    False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    has_server_default=True,
                    default_kind="auto_increment",
                    category="integer",
                ),
            ],
            primary_key=["actor_id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Sakila", errors, warnings, mode="strict")

        assert errors == []
        assert warnings == []

    def test_strict_mode_downgrades_unsupported_missing_columns_to_warning(self):
        reference = _metadata("postgres", _table(
            "address",
            [
                ColumnInfo("address_id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("location", "geometry", True, category="other"),
            ],
            primary_key=["address_id"],
        ))
        target = _metadata("mariadb", _table(
            "address",
            [ColumnInfo("address_id", "integer", False, is_primary_key=True, category="integer")],
            primary_key=["address_id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Makila", errors, warnings, mode="strict")

        assert errors == []
        assert "Makila: в address отсутствует колонка location" in warnings

    def test_strict_mode_cross_dbms_nullable_drift_on_optional_column_is_warning(self):
        """Sakila MySQL vs Pagila: address.location часто расходится по NULL в metadata."""
        reference = _metadata("mysql", _table(
            "address",
            [
                ColumnInfo("address_id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("location", "varchar", False, category="string"),
            ],
            primary_key=["address_id"],
        ))
        target = _metadata("postgresql", _table(
            "address",
            [
                ColumnInfo("address_id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("location", "varchar", True, category="string"),
            ],
            primary_key=["address_id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Pagila", errors, warnings, mode="strict")

        assert errors == []
        assert "Pagila: address.location отличается nullable" in warnings

    def test_strict_mode_reports_fk_and_unique_drift_as_warnings(self):
        reference_table = _table(
            "film_text",
            [ColumnInfo("film_id", "integer", False, category="integer")],
            primary_key=["film_id"],
        )
        reference_table.foreign_keys_out = [
            SimpleNamespace(from_column="film_id", to_table="film", to_column="film_id")
        ]
        reference_table.unique_constraints = [["film_id"]]
        reference = _metadata("postgres", reference_table)
        target = _metadata("mysql", _table(
            "film_text",
            [ColumnInfo("film_id", "integer", False, category="integer")],
            primary_key=["film_id"],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Sakila", errors, warnings, mode="strict")

        assert errors == []
        assert "Sakila: FK-связи таблицы film_text отличаются от эталона" in warnings
        assert "Sakila: UNIQUE constraints таблицы film_text отличаются от эталона" in warnings

    def test_schema_analyzer_normalizes_sakila_mysql_types(self):
        analyzer = SchemaAnalyzer()

        assert analyzer._categorize_data_type("tinyint(1)") == "boolean"
        assert analyzer._categorize_data_type("tinyint(3) unsigned") == "integer"
        assert analyzer._categorize_data_type("year") == "integer"

    def test_nullable_default_null_drift_is_ignored(self):
        reference = _metadata("mysql", _table(
            "orders",
            [ColumnInfo(
                "comment",
                "text",
                True,
                column_default="NULL",
                has_server_default=True,
                default_kind="default",
                category="string",
            )],
        ))
        target = _metadata("postgres", _table(
            "orders",
            [ColumnInfo("comment", "text", True, category="string")],
        ))
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Postgres", errors, warnings, mode="strict")

        assert errors == []
        assert warnings == []

    def test_strict_mode_normalizes_cross_db_check_constraint_syntax(self):
        reference = _metadata("mariadb", _table(
            "olist_order_reviews_dataset",
            [
                ColumnInfo("review_id", "char", False, is_primary_key=True, category="string"),
                ColumnInfo("order_id", "char", False, is_primary_key=True, category="string"),
                ColumnInfo("review_score", "integer", False, category="integer"),
            ],
            primary_key=["review_id", "order_id"],
        ))
        reference.tables["olist_order_reviews_dataset"].check_constraints = [
            "`review_score` between 1 and 5",
        ]
        target = _metadata("postgres", _table(
            "olist_order_reviews_dataset",
            [
                ColumnInfo("review_id", "char", False, is_primary_key=True, category="string"),
                ColumnInfo("order_id", "char", False, is_primary_key=True, category="string"),
                ColumnInfo("review_score", "integer", False, category="integer"),
            ],
            primary_key=["review_id", "order_id"],
        ))
        target.tables["olist_order_reviews_dataset"].check_constraints = [
            "review_id IS NOT NULL",
            "order_id IS NOT NULL",
            "review_score IS NOT NULL",
            "(((review_score >= 1) AND (review_score <= 5)))",
        ]
        validator = DatabaseGroupValidator.__new__(DatabaseGroupValidator)
        errors = []
        warnings = []

        validator._compare_metadata(
            reference,
            target,
            "Brazilian E-com Postgres",
            errors,
            warnings,
            mode="strict",
        )

        assert errors == []


class TestScenarioBundleResolverProfileSync:
    @pytest.mark.asyncio
    async def test_logical_db_connection_without_synced_profile_is_blocking_error(self):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Logical",
            schema_profile_id="profile-1",
            reference_connection_id="conn-1",
        )
        connection = _connection(
            "conn-1",
            "PostgreSQL",
            schema_profile_id=None,
            database_group=logical_db,
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo([connection]), _BundleRepo())

        with pytest.raises(ValueError, match="не синхронизирован schema_profile"):
            await resolver.resolve_for_connections(["conn-1"], scenario_template_id="mixed_light")

    @pytest.mark.asyncio
    async def test_resolver_uses_logical_db_reference_for_strict_validation(self, monkeypatch):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Logical",
            schema_profile_id="profile-1",
            reference_connection_id="conn-2",
        )
        connections = [
            _connection("conn-1", "MySQL", schema_profile_id="profile-1", database_group=logical_db),
            _connection("conn-2", "PostgreSQL", schema_profile_id="profile-1", database_group=logical_db),
        ]
        calls = {}

        async def fake_validate(self, connection_ids, reference_connection_id=None, mode="lenient"):
            calls["connection_ids"] = connection_ids
            calls["reference_connection_id"] = reference_connection_id
            calls["mode"] = mode
            return {"valid": True, "errors": [], "warnings": []}

        monkeypatch.setattr(
            "backend.database.scenario_bundle_resolver.DatabaseGroupValidator.validate_connections",
            fake_validate,
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo(connections), _BundleRepo())

        resolved = await resolver.resolve_for_connections(
            ["conn-1", "conn-2"],
            scenario_template_id="mixed_light",
        )

        assert resolved["schema_profile_id"] == "profile-1"
        assert calls == {
            "connection_ids": ["conn-1", "conn-2"],
            "reference_connection_id": "conn-2",
            "mode": "strict",
        }

    @pytest.mark.asyncio
    async def test_resolver_prefers_common_bundle_for_multi_connection_logical_db(self, monkeypatch):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Sakila",
            schema_profile_id="profile-1",
            reference_connection_id="conn-2",
            profile_status="confirmed",
            compatibility_status="valid_with_warnings",
        )
        connections = [
            _connection("conn-1", "Sakila", schema_profile_id="profile-1", database_group=logical_db),
            _connection("conn-2", "Pagila", schema_profile_id="profile-1", database_group=logical_db),
        ]
        requested = {}

        class _TrackingBundleRepo(_BundleRepo):
            async def get_bundle_for_profile_template(
                self,
                schema_profile_id,
                scenario_template_id,
                bundle_id=None,
                preferred_name=None,
            ):
                requested["preferred_name"] = preferred_name
                if preferred_name == "mixed_light::Sakila::common":
                    return _Bundle()
                return None

        async def fake_validate(self, connection_ids, reference_connection_id=None, mode="lenient"):
            return {"valid": True, "errors": [], "warnings": []}

        monkeypatch.setattr(
            "backend.database.scenario_bundle_resolver.DatabaseGroupValidator.validate_connections",
            fake_validate,
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo(connections), _TrackingBundleRepo())

        resolved = await resolver.resolve_for_connections(
            ["conn-1", "conn-2"],
            scenario_template_id="mixed_light",
        )

        assert requested["preferred_name"] == "mixed_light::Sakila::common"
        assert resolved["bundle"]["scenario_template_id"] == "mixed_light"

    @pytest.mark.asyncio
    async def test_resolver_requires_common_bundle_for_multi_connection_logical_db(self, monkeypatch):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Sakila",
            schema_profile_id="profile-1",
            reference_connection_id="conn-1",
            profile_status="confirmed",
            compatibility_status="valid",
        )
        connections = [
            _connection("conn-1", "Sakila", schema_profile_id="profile-1", database_group=logical_db),
            _connection("conn-2", "Pagila", schema_profile_id="profile-1", database_group=logical_db),
        ]

        async def fake_validate(self, connection_ids, reference_connection_id=None, mode="lenient"):
            return {"valid": True, "errors": [], "warnings": []}

        monkeypatch.setattr(
            "backend.database.scenario_bundle_resolver.DatabaseGroupValidator.validate_connections",
            fake_validate,
        )

        class _MissingCommonBundleRepo(_BundleRepo):
            async def get_bundle_for_profile_template(
                self,
                schema_profile_id,
                scenario_template_id,
                bundle_id=None,
                preferred_name=None,
            ):
                if preferred_name:
                    return None
                return await super().get_bundle_for_profile_template(
                    schema_profile_id,
                    scenario_template_id,
                    bundle_id=bundle_id,
                    preferred_name=preferred_name,
                )

        resolver = ScenarioBundleResolver(_ConnectionRepo(connections), _MissingCommonBundleRepo())

        with pytest.raises(ValueError, match="не найден common bundle"):
            await resolver.resolve_for_connections(
                ["conn-1", "conn-2"],
                scenario_template_id="mixed_light",
            )

    @pytest.mark.asyncio
    async def test_resolver_blocks_pending_review_connection(self):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Logical",
            schema_profile_id="profile-1",
            reference_connection_id="conn-1",
            profile_status="confirmed",
            compatibility_status="valid",
        )
        connection = _connection(
            "conn-1",
            "PostgreSQL",
            schema_profile_id="profile-1",
            database_group=logical_db,
            profile_source="pending_review",
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo([connection]), _BundleRepo())

        with pytest.raises(ValueError, match="не синхронизирован schema_profile"):
            await resolver.resolve_for_connections(["conn-1"], scenario_template_id="mixed_light")

    @pytest.mark.asyncio
    async def test_resolver_blocks_unconfirmed_database_group_state(self):
        logical_db = SimpleNamespace(
            id="logical-1",
            name="Logical",
            schema_profile_id="profile-1",
            reference_connection_id="conn-1",
            profile_status="needs_review",
            compatibility_status="unknown",
        )
        connection = _connection(
            "conn-1",
            "PostgreSQL",
            schema_profile_id="profile-1",
            database_group=logical_db,
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo([connection]), _BundleRepo())

        with pytest.raises(ValueError, match="требует проверки профиля"):
            await resolver.resolve_for_connections(["conn-1"], scenario_template_id="mixed_light")


class TestSchemaAnalyzerInsertSafe:
    def test_insert_safe_false_when_primary_key_has_no_database_default(self):
        table = _table(
            "payment",
            [
                ColumnInfo("payment_id", "smallint", False, is_primary_key=True, category="integer"),
                ColumnInfo("amount", "numeric", False, category="numeric"),
            ],
            primary_key=["payment_id"],
        )
        analyzer = SchemaAnalyzer.__new__(SchemaAnalyzer)
        assert analyzer._is_insert_safe(table) is False

    def test_insert_safe_true_when_primary_key_has_sequence_default(self):
        table = _table(
            "payment",
            [
                ColumnInfo(
                    "payment_id",
                    "smallint",
                    False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    has_server_default=True,
                    column_default="nextval('payment_payment_id_seq'::regclass)",
                    default_kind="serial",
                    category="integer",
                ),
                ColumnInfo("amount", "numeric", False, category="numeric"),
            ],
            primary_key=["payment_id"],
        )
        analyzer = SchemaAnalyzer.__new__(SchemaAnalyzer)
        assert analyzer._is_insert_safe(table) is True


class TestCommonCapabilityMetadata:
    def test_common_metadata_keeps_only_cross_database_safe_columns(self):
        reference_table = _table(
            "orders",
            [
                ColumnInfo("id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("amount", "numeric", False, category="numeric"),
                ColumnInfo("pg_only", "text", True, category="string"),
            ],
            primary_key=["id"],
            capabilities=["readable", "insert_safe"],
        )
        target_table = _table(
            "orders",
            [
                ColumnInfo("id", "integer", False, is_primary_key=True, category="integer"),
                ColumnInfo("amount", "numeric", False, category="numeric"),
                ColumnInfo("mysql_only", "text", True, category="string"),
            ],
            primary_key=["id"],
            capabilities=["readable", "insert_safe"],
        )
        generator = ScenarioGenerator()

        common = generator._build_common_capability_metadata(
            reference_metadata=_metadata("pg", reference_table),
            all_metadata=[_metadata("pg", reference_table), _metadata("mysql", target_table)],
        )

        assert set(common.tables["orders"].get_column(column).name for column in ["id", "amount"]) == {"id", "amount"}
        assert common.tables["orders"].get_column("pg_only") is None
        assert common.tables["orders"].get_column("mysql_only") is None

    def test_common_metadata_normalizes_check_constraints(self):
        mariadb_table = _table(
            "reviews",
            [ColumnInfo("review_score", "integer", False, category="integer")],
            capabilities=["readable", "insert_safe"],
        )
        mariadb_table.check_constraints = ["`review_score` between 1 and 5"]
        postgres_table = _table(
            "reviews",
            [ColumnInfo("review_score", "integer", False, category="integer")],
            capabilities=["readable", "insert_safe"],
        )
        postgres_table.check_constraints = [
            "review_score IS NOT NULL",
            "(((review_score >= 1) AND (review_score <= 5)))",
        ]
        generator = ScenarioGenerator()

        common = generator._build_common_capability_metadata(
            reference_metadata=_metadata("mariadb", mariadb_table),
            all_metadata=[
                _metadata("mariadb", mariadb_table),
                _metadata("postgres", postgres_table),
            ],
        )

        assert common.tables["reviews"].check_constraints == [
            "review_score >= 1 and review_score <= 5"
        ]
