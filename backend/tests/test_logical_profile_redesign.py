"""
Регрессионные тесты новой модели logical database/schema profile.
"""
from types import SimpleNamespace

import pytest

from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_generator import ScenarioGenerator
from backend.database.schema_analyzer import ColumnInfo, SchemaMetadata, TableInfo


def _connection(
    connection_id,
    name,
    *,
    schema_profile_id=None,
    logical_database=None,
    profile_source="inherited",
):
    return SimpleNamespace(
        id=connection_id,
        name=name,
        dbms_type="postgresql",
        schema_profile_id=schema_profile_id,
        schema_profile=SimpleNamespace(name="profile") if schema_profile_id else None,
        profile_source=profile_source,
        logical_database_id=logical_database.id if logical_database else None,
        logical_database=logical_database,
    )


def _metadata(connection_id, table):
    return SchemaMetadata(
        connection_id=connection_id,
        connection_name=connection_id,
        dbms_type="postgresql",
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
    async def get_bundle_for_profile_template(self, schema_profile_id, scenario_template_id):
        assert schema_profile_id == "profile-1"
        assert scenario_template_id == "mixed_light"
        return _Bundle()

    async def get_bundle(self, bundle_id):
        return _Bundle()


class TestLogicalDatabaseValidatorStrictMode:
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
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target", errors, warnings, mode="strict")

        assert "Target: в orders отсутствует колонка amount" in errors
        assert warnings == []

    def test_strict_mode_blocks_required_default_drift(self):
        reference = _metadata("ref", _table(
            "orders",
            [
                ColumnInfo(
                    "id",
                    "integer",
                    False,
                    is_primary_key=True,
                    is_auto_generated=True,
                    has_server_default=True,
                    default_kind="identity",
                    category="integer",
                ),
            ],
            primary_key=["id"],
        ))
        target = _metadata("target", _table(
            "orders",
            [ColumnInfo("id", "integer", False, is_primary_key=True, category="integer")],
            primary_key=["id"],
        ))
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
        errors = []
        warnings = []

        validator._compare_metadata(reference, target, "Target", errors, warnings, mode="strict")

        assert "Target: orders.id отличается server default/identity" in errors

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
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
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
        validator = LogicalDatabaseValidator.__new__(LogicalDatabaseValidator)
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
            logical_database=logical_db,
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
            _connection("conn-1", "MySQL", schema_profile_id="profile-1", logical_database=logical_db),
            _connection("conn-2", "PostgreSQL", schema_profile_id="profile-1", logical_database=logical_db),
        ]
        calls = {}

        async def fake_validate(self, connection_ids, reference_connection_id=None, mode="lenient"):
            calls["connection_ids"] = connection_ids
            calls["reference_connection_id"] = reference_connection_id
            calls["mode"] = mode
            return {"valid": True, "errors": [], "warnings": []}

        monkeypatch.setattr(
            "backend.database.scenario_bundle_resolver.LogicalDatabaseValidator.validate_connections",
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
            logical_database=logical_db,
            profile_source="pending_review",
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo([connection]), _BundleRepo())

        with pytest.raises(ValueError, match="не синхронизирован schema_profile"):
            await resolver.resolve_for_connections(["conn-1"], scenario_template_id="mixed_light")

    @pytest.mark.asyncio
    async def test_resolver_blocks_unconfirmed_logical_database_state(self):
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
            logical_database=logical_db,
        )
        resolver = ScenarioBundleResolver(_ConnectionRepo([connection]), _BundleRepo())

        with pytest.raises(ValueError, match="требует проверки профиля"):
            await resolver.resolve_for_connections(["conn-1"], scenario_template_id="mixed_light")


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
