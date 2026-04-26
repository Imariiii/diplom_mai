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
):
    return SimpleNamespace(
        id=connection_id,
        name=name,
        dbms_type="postgresql",
        schema_profile_id=schema_profile_id,
        schema_profile=SimpleNamespace(name="profile") if schema_profile_id else None,
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
