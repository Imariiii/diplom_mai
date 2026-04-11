"""
Bootstrap нового profile-centric слоя сценариев.
"""
from typing import List, Optional

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.profile_repository import ProfileRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.schema_profile_resolver import SchemaProfileResolver
from backend.database.scenario_generator import ScenarioGenerator


REFERENCE_CONNECTION_PRIORITY = {
    "sakila_like": ["pagila", "sakila", "sakila_mariadb"],
    "olist_like": ["brazil_e-com", "olist", "olist_postgres"],
}


class LogicalScenarioBootstrap:
    """Инициализация и мягкая миграция logical scenario layer."""

    def __init__(
        self,
        connection_repository: ConnectionRepository,
        profile_repository: ProfileRepository,
        bundle_repository: ScenarioBundleRepository,
    ):
        self.connection_repository = connection_repository
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

    async def bootstrap(self) -> None:
        """Запустить seed и мягкую миграцию существующих сущностей."""
        await self.profile_repository.seed_builtin_templates()
        await self.profile_repository.seed_builtin_profiles()
        await self._assign_profiles_to_existing_connections()
        await self._ensure_reference_connections()
        await self._ensure_builtin_bundles()

    async def _assign_profiles_to_existing_connections(self) -> None:
        connections = await self.connection_repository.get_all_connections()
        for connection in connections:
            try:
                preview = await self.profile_resolver.build_connection_profile_preview(str(connection.id))
                suggested_profile = preview["suggested_profile"]
                profile_id = suggested_profile.get("existing_profile_id")
                should_auto_assign = bool(profile_id and suggested_profile.get("confidence", 0) >= 0.75)
                await self.connection_repository.update_connection(
                    connection_id=str(connection.id),
                    schema_profile_id=profile_id if should_auto_assign else (
                        str(connection.schema_profile_id) if connection.schema_profile_id else None
                    ),
                    detected_profile_name=suggested_profile["name"],
                    profile_confidence=suggested_profile["confidence"],
                    profile_source='auto' if should_auto_assign or not connection.profile_source else connection.profile_source,
                )
            except Exception as exc:
                print(f"[LOGICAL_BOOTSTRAP] Не удалось определить профиль для {connection.name}: {exc}")

    async def _ensure_reference_connections(self) -> None:
        profiles = await self.profile_repository.list_profiles()
        connections = await self.connection_repository.get_all_connections()

        for profile in profiles:
            if profile.reference_connection_id:
                continue

            assigned_connections = [
                connection for connection in connections
                if connection.schema_profile_id and str(connection.schema_profile_id) == str(profile.id)
            ]
            reference_connection = self._pick_reference_connection(profile.name, assigned_connections)
            if reference_connection:
                await self.profile_repository.update_profile(
                    profile_id=str(profile.id),
                    reference_connection_id=str(reference_connection.id),
                )

    async def _ensure_builtin_bundles(self) -> None:
        profiles = await self.profile_repository.list_profiles()
        templates = [
            template
            for template in await self.profile_repository.list_templates()
            if template.is_builtin == 't'
        ]

        for profile in profiles:
            if not profile.reference_connection_id:
                continue

            existing_bundles = await self.bundle_repository.list_bundles(schema_profile_id=str(profile.id))
            existing_builtin_template_ids = {
                bundle.scenario_template_id
                for bundle in existing_bundles
                if bundle.is_builtin == 't'
            }
            missing_or_incomplete_template_ids = [
                template.id for template in templates
                if template.id not in existing_builtin_template_ids
                or any(
                    bundle.scenario_template_id == template.id
                    and bundle.is_builtin == 't'
                    and (not bundle.queries or not bundle.indexes)
                    for bundle in existing_bundles
                )
            ]
            if not missing_or_incomplete_template_ids:
                continue

            try:
                await self.generator.generate_bundles_for_profile(
                    schema_profile_id=str(profile.id),
                    reference_connection_id=str(profile.reference_connection_id),
                    scenario_types=missing_or_incomplete_template_ids,
                )
            except Exception as exc:
                print(f"[LOGICAL_BOOTSTRAP] Не удалось сгенерировать bundles для {profile.name}: {exc}")

    def _pick_reference_connection(self, profile_name: str, connections: List) -> Optional[object]:
        if not connections:
            return None

        preferred_names = REFERENCE_CONNECTION_PRIORITY.get(profile_name, [])
        lower_map = {connection.name.lower(): connection for connection in connections}
        for preferred_name in preferred_names:
            if preferred_name.lower() in lower_map:
                return lower_map[preferred_name.lower()]
        return sorted(connections, key=lambda item: item.name)[0]
