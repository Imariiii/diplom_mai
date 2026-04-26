"""
Bootstrap нового profile-centric слоя сценариев.
"""
from typing import List, Optional

from backend.database.logical_database_provisioner import LogicalDatabaseProvisioner
from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.repository.profile_repository import ProfileRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.scenario_generator import SCENARIO_GENERATOR_VERSION, ScenarioGenerator


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
        logical_database_repository: Optional[LogicalDatabaseRepository] = None,
    ):
        self.connection_repository = connection_repository
        self.profile_repository = profile_repository
        self.bundle_repository = bundle_repository
        self.logical_database_repository = logical_database_repository
        self.generator = ScenarioGenerator(
            connection_repo=connection_repository,
            bundle_repository=bundle_repository,
        )
        self.provisioner = (
            LogicalDatabaseProvisioner(
                connection_repository=connection_repository,
                logical_database_repository=logical_database_repository,
                profile_repository=profile_repository,
                bundle_repository=bundle_repository,
            )
            if logical_database_repository else None
        )
        self.validator = LogicalDatabaseValidator(connection_repository)

    async def bootstrap(self) -> None:
        """Запустить seed и мягкую миграцию существующих сущностей."""
        await self.profile_repository.seed_builtin_templates()
        await self._auto_provision_existing_logical_databases()
        await self._sync_logical_databases_profiles()
        await self._ensure_logical_database_reference_state()
        await self._ensure_reference_connections()
        await self._ensure_builtin_bundles()

    async def _auto_provision_existing_logical_databases(self) -> None:
        """Автоматически создать profile/bundle для уже существующих logical database."""
        if not self.provisioner or not self.logical_database_repository:
            return

        logical_databases = await self.logical_database_repository.get_all_with_connections()
        for logical_database in logical_databases:
            active_connections = [
                connection
                for connection in logical_database.connections
                if connection.is_active == 't'
            ]
            if not active_connections:
                continue
            if logical_database.schema_profile_id:
                continue

            try:
                await self.provisioner.ensure_logical_database_ready(str(logical_database.id))
            except Exception as exc:
                print(
                    f"[LOGICAL_BOOTSTRAP] Не удалось автоматически подготовить "
                    f"{logical_database.name}: {exc}"
                )

    async def _sync_logical_databases_profiles(self) -> None:
        """Синхронизировать profile_id только если strict validation подтверждает совместимость."""
        if not self.logical_database_repository:
            return

        logical_databases = await self.logical_database_repository.get_all_with_connections()
        for logical_database in logical_databases:
            active_connections = [
                connection
                for connection in logical_database.connections
                if connection.is_active == 't' and connection.schema_profile_id
            ]
            profile_ids = {str(connection.schema_profile_id) for connection in active_connections}
            if len(profile_ids) != 1:
                continue

            target_profile_id = next(iter(profile_ids))
            if str(logical_database.schema_profile_id) == target_profile_id:
                continue

            reference_connection = next(
                (
                    connection for connection in active_connections
                    if str(connection.schema_profile_id) == target_profile_id
                ),
                None,
            )
            if not reference_connection:
                continue
            try:
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
                    continue
                await self.logical_database_repository.assign_profile(
                    logical_db_id=str(logical_database.id),
                    schema_profile_id=target_profile_id,
                    schema_profile_name=(
                        reference_connection.schema_profile.name
                        if reference_connection and reference_connection.schema_profile
                        else None
                    ),
                    profile_source='inherited',
                    reference_connection_id=str(reference_connection.id),
                    profile_status="confirmed",
                    compatibility_status=(
                        "valid_with_warnings" if compatibility.get("warnings") else "valid"
                    ),
                    compatibility_report=compatibility,
                )
            except Exception as exc:
                print(
                    f"[LOGICAL_BOOTSTRAP] Не удалось синхронизировать профиль "
                    f"{logical_database.name}: {exc}"
                )

    async def _ensure_logical_database_reference_state(self) -> None:
        """Восстановить reference/status для существующих logical database без слепой синхронизации."""
        if not self.logical_database_repository:
            return

        logical_databases = await self.logical_database_repository.get_all_with_connections()
        for logical_database in logical_databases:
            active_connections = [
                connection
                for connection in logical_database.connections
                if connection.is_active == 't'
            ]
            if not active_connections:
                continue

            reference_connection = self._pick_logical_database_reference(logical_database, active_connections)
            if not reference_connection:
                continue

            try:
                compatibility = await self.validator.validate_connections(
                    [str(connection.id) for connection in active_connections],
                    reference_connection_id=str(reference_connection.id),
                    mode="strict",
                )
                await self.logical_database_repository.update_profile_state(
                    logical_db_id=str(logical_database.id),
                    profile_status="confirmed" if compatibility.get("valid") else "incompatible",
                    compatibility_status=(
                        "invalid"
                        if not compatibility.get("valid")
                        else ("valid_with_warnings" if compatibility.get("warnings") else "valid")
                    ),
                    compatibility_report=compatibility,
                    reference_connection_id=str(reference_connection.id),
                )
            except Exception as exc:
                print(
                    f"[LOGICAL_BOOTSTRAP] Не удалось проверить logical database "
                    f"{logical_database.name}: {exc}"
                )

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
                    and (
                        not bundle.queries
                        or not bundle.indexes
                        or str(bundle.generated_from_connection_id) != str(profile.reference_connection_id)
                        or bundle.generation_source != SCENARIO_GENERATOR_VERSION
                    )
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

    def _pick_logical_database_reference(self, logical_database, active_connections: List) -> Optional[object]:
        if not active_connections:
            return None
        if getattr(logical_database, "reference_connection_id", None):
            for connection in active_connections:
                if str(connection.id) == str(logical_database.reference_connection_id):
                    return connection
        if logical_database.schema_profile and logical_database.schema_profile.reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == str(logical_database.schema_profile.reference_connection_id):
                    return connection
        return sorted(active_connections, key=lambda item: item.name)[0]
