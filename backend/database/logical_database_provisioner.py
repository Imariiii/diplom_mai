"""
Автопровижининг logical database:
первое подключение -> анализ -> auto profile -> auto bundle generation.
"""
import re
from typing import Any, Dict, List, Optional

from backend.database.logical_scenarios import LOGICAL_SCENARIO_TEMPLATE_IDS
from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.repository.profile_repository import ProfileRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.schema_profile_resolver import SchemaProfileResolver
from backend.database.scenario_generator import ScenarioGenerator


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

        reference_connection = self._pick_reference_connection(
            active_connections=active_connections,
            reference_connection_id=reference_connection_id,
        )

        profile = None
        profile_was_created = False
        if logical_database.schema_profile_id:
            profile = await self.profile_repository.get_profile_by_id(
                str(logical_database.schema_profile_id)
            )

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
            )

        if profile and (
            not profile.reference_connection_id
            or str(profile.reference_connection_id) != str(reference_connection.id)
        ):
            profile = await self.profile_repository.update_profile(
                profile_id=str(profile.id),
                description=profile.description,
                reference_connection_id=str(reference_connection.id),
            )

        should_generate = profile_was_created or await self._bundles_missing_for_profile(str(profile.id))
        generated_bundles: List[Dict[str, Any]] = []
        if should_generate:
            generated_bundles = await self.generator.generate_bundles_for_profile(
                schema_profile_id=str(profile.id),
                reference_connection_id=str(reference_connection.id),
            )

        logical_database = await self.logical_database_repository.get_by_id(str(logical_database.id))
        return {
            "logical_database": logical_database,
            "profile": profile,
            "bundles": generated_bundles,
            "generated_count": len(generated_bundles),
            "used_connection_id": str(reference_connection.id),
        }

    async def _resolve_or_create_profile(self, logical_database, reference_connection):
        """Получить существующий профиль по анализу схемы или создать новый."""
        preview = await self.profile_resolver.build_connection_profile_preview(str(reference_connection.id))
        suggestion = preview["suggested_profile"]

        profile_name = suggestion["name"]
        if suggestion.get("confidence", 0) < 0.45:
            profile_name = self._build_profile_name_from_logical_db(logical_database.name)

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

    async def _bundles_missing_for_profile(self, schema_profile_id: str) -> bool:
        """Проверить, что для профиля уже созданы канонические bundle'ы по всем builtin templates."""
        bundles = await self.bundle_repository.list_bundles(schema_profile_id=schema_profile_id)
        generated_templates = {
            bundle.scenario_template_id
            for bundle in bundles
            if bundle.is_builtin == 't' and bundle.queries
        }
        return any(template_id not in generated_templates for template_id in LOGICAL_SCENARIO_TEMPLATE_IDS)

    def _pick_reference_connection(self, active_connections, reference_connection_id: Optional[str] = None):
        """Выбрать эталонное подключение для анализа и генерации bundle'ов."""
        if reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == reference_connection_id:
                    return connection
            raise ValueError("reference_connection_id не принадлежит logical database")
        return sorted(active_connections, key=lambda connection: connection.name)[0]

    def _build_profile_name_from_logical_db(self, logical_database_name: str) -> str:
        """Построить machine-friendly имя профиля из названия logical database."""
        normalized = re.sub(r"[^a-z0-9]+", "_", logical_database_name.lower()).strip("_")
        if not normalized:
            normalized = "custom_schema"
        if not normalized.endswith("_like"):
            normalized = f"{normalized}_like"
        return normalized

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
