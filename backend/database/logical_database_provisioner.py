"""
Автопровижининг logical database:
первое подключение -> анализ -> auto profile -> auto bundle generation.
"""
import re
from typing import Any, Dict, List, Optional

from backend.database.logical_scenarios import LOGICAL_SCENARIO_TEMPLATE_IDS
from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.repository.profile_repository import ProfileRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.schema_profile_resolver import SchemaProfileResolver
from backend.database.scenario_generator import SCENARIO_GENERATOR_VERSION, ScenarioGenerator


class LogicalDatabaseProvisioner:
    """Обеспечивает автоматическое создание профиля и bundle'ов для logical database."""

    def __init__(
        self,
        connection_repository: ConnectionRepository,
        logical_database_repository: LogicalDatabaseRepository,
        profile_repository: ProfileRepository,
        bundle_repository: ScenarioBundleRepository,
    ):
        self.connection_repository = connection_repository
        self.logical_database_repository = logical_database_repository
        self.profile_repository = profile_repository
        self.bundle_repository = bundle_repository
        self.profile_resolver = SchemaProfileResolver(
            connection_repo=connection_repository,
            profile_repository=profile_repository,
        )
        self.generator = ScenarioGenerator(
            connection_repo=connection_repository,
            bundle_repository=bundle_repository,
        )
        self.validator = LogicalDatabaseValidator(connection_repository)

    async def ensure_logical_database_ready(
        self,
        logical_database_id: str,
        reference_connection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Автоматически подготовить logical database к запуску сценариев."""
        logical_database = await self.logical_database_repository.get_by_id(logical_database_id)
        if not logical_database:
            raise ValueError("Логическая БД не найдена")

        active_connections = [
            connection
            for connection in (logical_database.connections or [])
            if connection.is_active == 't'
        ]
        if not active_connections:
            return {
                "logical_database": logical_database,
                "profile": None,
                "bundles": [],
                "generated_count": 0,
                "used_connection_id": None,
            }

        profile = None
        profile_was_created = False
        if logical_database.schema_profile_id:
            profile = await self.profile_repository.get_profile_by_id(
                str(logical_database.schema_profile_id)
            )

        reference_connection = self._pick_reference_connection(
            active_connections=active_connections,
            reference_connection_id=reference_connection_id,
            logical_database=logical_database,
            profile=profile,
        )

        compatibility = None
        if len(active_connections) > 1:
            compatibility = await self.validator.validate_connections(
                [str(connection.id) for connection in active_connections],
                reference_connection_id=str(reference_connection.id),
                mode="strict",
            )
            if not compatibility.get("valid"):
                await self.logical_database_repository.update_profile_state(
                    logical_db_id=str(logical_database.id),
                    profile_status="incompatible",
                    compatibility_status="invalid",
                    compatibility_report=compatibility,
                    reference_connection_id=str(reference_connection.id),
                )
                raise ValueError(
                    "Подключения logical database несовместимы: "
                    + "; ".join(compatibility.get("errors", []))
                )
        else:
            compatibility = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "reference_connection_id": str(reference_connection.id),
                "reference_connection_name": reference_connection.name,
                "mode": "strict",
                "connections": [
                    {
                        "id": str(reference_connection.id),
                        "name": reference_connection.name,
                        "dbms_type": reference_connection.dbms_type,
                    }
                ],
            }

        if not profile:
            profile, profile_was_created = await self._resolve_or_create_profile(
                logical_database=logical_database,
                reference_connection=reference_connection,
            )
            logical_database = await self.logical_database_repository.assign_profile(
                logical_db_id=str(logical_database.id),
                schema_profile_id=str(profile.id),
                schema_profile_name=profile.name,
                profile_source='auto',
                reference_connection_id=str(reference_connection.id),
                profile_status="confirmed",
                compatibility_status=self._compatibility_status(compatibility),
                compatibility_report=compatibility,
            )
        else:
            logical_database = await self.logical_database_repository.assign_profile(
                logical_db_id=str(logical_database.id),
                schema_profile_id=str(profile.id),
                schema_profile_name=profile.name,
                profile_source='inherited',
                reference_connection_id=str(reference_connection.id),
                profile_status="confirmed",
                compatibility_status=self._compatibility_status(compatibility),
                compatibility_report=compatibility,
            )

        if profile and not profile.reference_connection_id:
            profile = await self.profile_repository.update_profile(
                profile_id=str(profile.id),
                description=profile.description,
                reference_connection_id=str(reference_connection.id),
            )

        should_generate = profile_was_created or await self._bundles_missing_for_profile(
            str(profile.id),
            str(reference_connection.id),
        )
        generated_bundles: List[Dict[str, Any]] = []
        if should_generate:
            generated_bundles = await self.generator.generate_bundles_for_logical_database(
                logical_database_id=str(logical_database.id),
                scenario_types=None,
            )

        logical_database = await self.logical_database_repository.get_by_id(str(logical_database.id))
        return {
            "logical_database": logical_database,
            "profile": profile,
            "bundles": generated_bundles,
            "generated_count": len(generated_bundles),
            "used_connection_id": str(reference_connection.id),
            "compatibility": compatibility if len(active_connections) > 1 else None,
        }

    async def _resolve_or_create_profile(self, logical_database, reference_connection):
        """Создать logical-DB scoped профиль по анализу схемы reference connection."""
        preview = await self.profile_resolver.build_connection_profile_preview(str(reference_connection.id))
        suggestion = preview["suggested_profile"]

        profile_name = self._build_profile_name_from_logical_db(
            logical_database.name,
            logical_database_id=str(logical_database.id),
            detected_name=suggestion["name"],
        )
        if suggestion.get("confidence", 0) < 0.45:
            profile_name = self._build_profile_name_from_logical_db(
                logical_database.name,
                logical_database_id=str(logical_database.id),
            )

        existing_profile = await self.profile_repository.get_profile_by_name(profile_name)
        if existing_profile:
            return existing_profile, False

        profile = await self.profile_repository.create_profile(
            name=profile_name,
            description=self._build_profile_description(
                logical_database_name=logical_database.name,
                suggested_description=suggestion.get("description"),
            ),
            reference_connection_id=str(reference_connection.id),
            is_builtin=False,
        )
        return profile, True

    async def _bundles_missing_for_profile(
        self,
        schema_profile_id: str,
        reference_connection_id: str,
    ) -> bool:
        """Проверить, что для профиля уже созданы канонические bundle'ы по всем builtin templates."""
        bundles = await self.bundle_repository.list_bundles(schema_profile_id=schema_profile_id)
        generated_templates = {
            bundle.scenario_template_id
            for bundle in bundles
            if bundle.is_builtin == 't'
            and bundle.queries
            and str(bundle.generated_from_connection_id) == reference_connection_id
            and bundle.generation_source == SCENARIO_GENERATOR_VERSION
        }
        return any(template_id not in generated_templates for template_id in LOGICAL_SCENARIO_TEMPLATE_IDS)

    def _pick_reference_connection(
        self,
        active_connections,
        reference_connection_id: Optional[str] = None,
        logical_database=None,
        profile=None,
    ):
        """Выбрать эталонное подключение для анализа и генерации bundle'ов."""
        if reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == reference_connection_id:
                    return connection
            raise ValueError("reference_connection_id не принадлежит logical database")
        if logical_database and logical_database.reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == str(logical_database.reference_connection_id):
                    return connection
        if profile and profile.reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == str(profile.reference_connection_id):
                    return connection
        return sorted(active_connections, key=lambda connection: connection.name)[0]

    def _build_profile_name_from_logical_db(
        self,
        logical_database_name: str,
        logical_database_id: Optional[str] = None,
        detected_name: Optional[str] = None,
    ) -> str:
        """Построить machine-friendly имя профиля из названия logical database."""
        base = detected_name or logical_database_name
        normalized = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
        if not normalized:
            normalized = "custom_schema"
        if not normalized.endswith("_like"):
            normalized = f"{normalized}_like"
        if logical_database_id:
            suffix = logical_database_id.replace("-", "")[:8]
            normalized = f"{normalized}_{suffix}"
        return normalized[:100]

    def _compatibility_status(self, compatibility: Optional[Dict[str, Any]]) -> str:
        if not compatibility:
            return "unknown"
        if not compatibility.get("valid"):
            return "invalid"
        if compatibility.get("warnings"):
            return "valid_with_warnings"
        return "valid"

    def _build_profile_description(
        self,
        logical_database_name: str,
        suggested_description: Optional[str],
    ) -> str:
        """Построить описание автоматически созданного профиля."""
        if suggested_description and "Автоопределение не смогло" not in suggested_description:
            return suggested_description
        return (
            f"Автоматически созданный профиль модели данных для logical database "
            f"'{logical_database_name}'."
        )
