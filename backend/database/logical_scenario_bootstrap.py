"""
Bootstrap нового profile-centric слоя сценариев.
"""
from typing import List, Optional

from backend.database.database_group_provisioner import DatabaseGroupProvisioner
from backend.database.database_group_validator import DatabaseGroupValidator
from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.database_group_repository import DatabaseGroupRepository
from backend.database.repository.profile_repository import ProfileRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository
from backend.database.logical_scenarios import (
    AUTO_GENERATED_SCENARIO_TEMPLATE_IDS,
    MANUAL_OLTP_GENERATION_SOURCE,
    MANUAL_OLTP_TEMPLATE_ID,
)
from backend.database.oltp_transaction_seeds import (
    build_manual_oltp_bundle_payload,
    is_olist_profile,
    is_sakila_profile,
)
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
        database_group_repository: Optional[DatabaseGroupRepository] = None,
    ):
        self.connection_repository = connection_repository
        self.profile_repository = profile_repository
        self.bundle_repository = bundle_repository
        self.database_group_repository = database_group_repository
        self.generator = ScenarioGenerator(
            connection_repo=connection_repository,
            bundle_repository=bundle_repository,
        )
        self.provisioner = (
            DatabaseGroupProvisioner(
                connection_repository=connection_repository,
                database_group_repository=database_group_repository,
                profile_repository=profile_repository,
                bundle_repository=bundle_repository,
            )
            if database_group_repository else None
        )
        self.validator = DatabaseGroupValidator(connection_repository)

    async def bootstrap(self) -> None:
        """Запустить seed и мягкую миграцию существующих сущностей."""
        await self.profile_repository.seed_builtin_templates()
        await self._auto_provision_existing_database_groups()
        await self._sync_database_groups_profiles()
        await self._ensure_database_group_reference_state()
        await self._ensure_reference_connections()
        await self._ensure_builtin_bundles()
        await self._ensure_manual_oltp_bundles()

    async def _auto_provision_existing_database_groups(self) -> None:
        """Автоматически создать profile/bundle для уже существующих database group."""
        if not self.provisioner or not self.database_group_repository:
            return

        database_groups = await self.database_group_repository.get_all_with_connections()
        for database_group in database_groups:
            if any(
                connection.is_active == 't' and connection.profile_source == "pending_review"
                for connection in database_group.connections
            ):
                continue
            active_connections = [
                connection
                for connection in database_group.connections
                if connection.is_active == 't'
            ]
            if not active_connections:
                continue
            if database_group.schema_profile_id:
                continue

            try:
                await self.provisioner.ensure_database_group_ready(str(database_group.id))
            except Exception as exc:
                print(
                    f"[LOGICAL_BOOTSTRAP] Не удалось автоматически подготовить "
                    f"{database_group.name}: {exc}"
                )

    async def _sync_database_groups_profiles(self) -> None:
        """Синхронизировать profile_id только если strict validation подтверждает совместимость."""
        if not self.database_group_repository:
            return

        database_groups = await self.database_group_repository.get_all_with_connections()
        for database_group in database_groups:
            active_connections = [
                connection
                for connection in database_group.connections
                if (
                    connection.is_active == 't'
                    and connection.schema_profile_id
                    and connection.profile_source != "pending_review"
                )
            ]
            profile_ids = {str(connection.schema_profile_id) for connection in active_connections}
            if len(profile_ids) != 1:
                continue

            target_profile_id = next(iter(profile_ids))
            if str(database_group.schema_profile_id) == target_profile_id:
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
                    await self.database_group_repository.update_profile_state(
                        database_group_id=str(database_group.id),
                        profile_status="incompatible",
                        compatibility_status="invalid",
                        compatibility_report=compatibility,
                        reference_connection_id=str(reference_connection.id),
                    )
                    continue
                await self.database_group_repository.assign_profile(
                    database_group_id=str(database_group.id),
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
                    f"{database_group.name}: {exc}"
                )

    async def _ensure_database_group_reference_state(self) -> None:
        """Восстановить reference/status для существующих database group без слепой синхронизации."""
        if not self.database_group_repository:
            return

        database_groups = await self.database_group_repository.get_all_with_connections()
        for database_group in database_groups:
            active_connections = [
                connection
                for connection in database_group.connections
                if connection.is_active == 't'
            ]
            if not active_connections:
                continue

            reference_connection = self._pick_database_group_reference(database_group, active_connections)
            if not reference_connection:
                continue

            try:
                compatibility = await self.validator.validate_connections(
                    [str(connection.id) for connection in active_connections],
                    reference_connection_id=str(reference_connection.id),
                    mode="strict",
                )
                has_pending_review = any(
                    connection.profile_source == "pending_review"
                    for connection in active_connections
                )
                has_profile = bool(database_group.schema_profile_id)
                await self.database_group_repository.update_profile_state(
                    database_group_id=str(database_group.id),
                    profile_status=(
                        "confirmed"
                        if compatibility.get("valid") and has_profile and not has_pending_review
                        else ("needs_review" if compatibility.get("valid") else "incompatible")
                    ),
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
                    f"[LOGICAL_BOOTSTRAP] Не удалось проверить database group "
                    f"{database_group.name}: {exc}"
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
        all_templates = await self.profile_repository.list_templates()
        auto_template_ids = set(AUTO_GENERATED_SCENARIO_TEMPLATE_IDS)
        templates = [
            template
            for template in all_templates
            if template.id in auto_template_ids
        ]

        logical_profile_ids = set()
        if self.database_group_repository:
            database_groups = await self.database_group_repository.get_all_with_connections()
            for database_group in database_groups:
                if not database_group.schema_profile_id:
                    continue
                if getattr(database_group, "profile_status", None) != "confirmed":
                    continue
                if getattr(database_group, "compatibility_status", None) == "invalid":
                    continue

                profile_id = str(database_group.schema_profile_id)
                logical_profile_ids.add(profile_id)
                existing_bundles = await self.bundle_repository.list_bundles(schema_profile_id=profile_id)
                missing_or_incomplete_template_ids = self._missing_or_incomplete_template_ids(
                    templates=templates,
                    existing_bundles=existing_bundles,
                    expected_name_builder=(
                        lambda template_id, name=database_group.name: f"{template_id}::{name}::common"
                    ),
                )
                if not missing_or_incomplete_template_ids:
                    continue

                try:
                    await self.generator.generate_bundles_for_database_group(
                        database_group_id=str(database_group.id),
                        scenario_types=missing_or_incomplete_template_ids,
                    )
                except Exception as exc:
                    print(
                        f"[LOGICAL_BOOTSTRAP] Не удалось сгенерировать common bundles "
                        f"для database group {database_group.name}: {exc}"
                    )

        for profile in profiles:
            if str(profile.id) in logical_profile_ids:
                continue
            if not profile.reference_connection_id:
                continue

            existing_bundles = await self.bundle_repository.list_bundles(schema_profile_id=str(profile.id))
            missing_or_incomplete_template_ids = self._missing_or_incomplete_template_ids(
                templates=templates,
                existing_bundles=existing_bundles,
                expected_name_builder=(
                    lambda template_id, profile_name=profile.name: f"{template_id}::{profile_name}::canonical"
                ),
                reference_connection_id=str(profile.reference_connection_id),
            )
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

    def _missing_or_incomplete_template_ids(
        self,
        templates: List,
        existing_bundles: List,
        expected_name_builder,
        reference_connection_id: Optional[str] = None,
    ) -> List[str]:
        """Найти builtin templates, для которых bundle отсутствует или устарел."""
        missing_or_incomplete_template_ids: List[str] = []
        for template in templates:
            bundle = next(
                (
                    item for item in existing_bundles
                    if item.scenario_template_id == template.id and item.is_builtin == 't'
                ),
                None,
            )
            if not bundle:
                missing_or_incomplete_template_ids.append(template.id)
                continue
            if not self._is_bundle_complete(bundle):
                missing_or_incomplete_template_ids.append(template.id)
                continue
            if bundle.generation_source != SCENARIO_GENERATOR_VERSION:
                missing_or_incomplete_template_ids.append(template.id)
                continue
            if bundle.name != expected_name_builder(template.id):
                missing_or_incomplete_template_ids.append(template.id)
                continue
            if reference_connection_id and str(bundle.generated_from_connection_id) != reference_connection_id:
                missing_or_incomplete_template_ids.append(template.id)
                continue
        return missing_or_incomplete_template_ids

    def _is_bundle_complete(self, bundle) -> bool:
        """Проверить, что bundle содержит достаточно данных для своего workload_mode."""
        workload_mode = (bundle.workload_mode or "query").strip().lower()
        if workload_mode == "transaction":
            transactions = bundle.transactions or []
            if not transactions:
                return False
            return all((transaction.steps or []) for transaction in transactions)
        if not bundle.queries:
            return False
        return bool(bundle.indexes)

    async def _ensure_manual_oltp_bundles(self) -> None:
        """Создать или обновить ручные OLTP transaction-bundle для Sakila и E-com."""
        targets = []

        if self.database_group_repository:
            database_groups = await self.database_group_repository.get_all_with_connections()
            for database_group in database_groups:
                if not database_group.schema_profile_id:
                    continue
                if getattr(database_group, "profile_status", None) != "confirmed":
                    continue
                if getattr(database_group, "compatibility_status", None) == "invalid":
                    continue
                profile = await self.profile_repository.get_profile_by_id(
                    str(database_group.schema_profile_id)
                )
                if not profile:
                    continue
                if not (
                    is_sakila_profile(profile.name, database_group.name)
                    or is_olist_profile(profile.name, database_group.name)
                ):
                    continue
                reference_connection = self._pick_database_group_reference(
                    database_group,
                    [
                        connection for connection in database_group.connections
                        if connection.is_active == 't'
                    ],
                )
                if not reference_connection:
                    continue
                targets.append({
                    "schema_profile_id": str(profile.id),
                    "profile_name": profile.name,
                    "scope_name": database_group.name,
                    "variant": "common",
                    "database_group_name": database_group.name,
                    "reference_connection_id": str(reference_connection.id),
                })

        profiles = await self.profile_repository.list_profiles()
        covered_profile_ids = {target["schema_profile_id"] for target in targets}
        for profile in profiles:
            if str(profile.id) in covered_profile_ids:
                continue
            if not profile.reference_connection_id:
                continue
            if not (is_sakila_profile(profile.name) or is_olist_profile(profile.name)):
                continue
            targets.append({
                "schema_profile_id": str(profile.id),
                "profile_name": profile.name,
                "scope_name": profile.name,
                "variant": "canonical",
                "database_group_name": None,
                "reference_connection_id": str(profile.reference_connection_id),
            })

        for target in targets:
            await self._upsert_manual_oltp_bundle_for_target(target)

    async def _upsert_manual_oltp_bundle_for_target(self, target: dict) -> None:
        """Идемпотентно применить manual OLTP seed к одному профилю."""
        payload = build_manual_oltp_bundle_payload(
            profile_name=target["profile_name"],
            scope_name=target["scope_name"],
            variant=target["variant"],
            database_group_name=target.get("database_group_name"),
        )
        if not payload:
            return

        existing_bundles = await self.bundle_repository.list_bundles(
            schema_profile_id=target["schema_profile_id"],
            scenario_template_id=MANUAL_OLTP_TEMPLATE_ID,
        )
        bundle = next(
            (item for item in existing_bundles if item.name == payload["name"]),
            None,
        )
        if bundle and bundle.generation_source == "manual_variant":
            return

        try:
            await self.bundle_repository.upsert_generated_bundle(
                schema_profile_id=target["schema_profile_id"],
                scenario_template_id=payload["scenario_template_id"],
                name=payload["name"],
                description=payload["description"],
                generation_source=payload["generation_source"],
                generated_from_connection_id=target["reference_connection_id"],
                queries=payload["queries"],
                indexes=payload["indexes"],
                transactions=payload["transactions"],
                workload_mode=payload["workload_mode"],
                activate=True,
                is_builtin=False,
            )
        except Exception as exc:
            print(
                f"[LOGICAL_BOOTSTRAP] Не удалось применить manual OLTP bundle "
                f"{payload['name']}: {exc}"
            )

    def _pick_reference_connection(self, profile_name: str, connections: List) -> Optional[object]:
        if not connections:
            return None

        preferred_names = REFERENCE_CONNECTION_PRIORITY.get(profile_name, [])
        lower_map = {connection.name.lower(): connection for connection in connections}
        for preferred_name in preferred_names:
            if preferred_name.lower() in lower_map:
                return lower_map[preferred_name.lower()]
        return sorted(connections, key=lambda item: item.name)[0]

    def _pick_database_group_reference(self, database_group, active_connections: List) -> Optional[object]:
        if not active_connections:
            return None
        if getattr(database_group, "reference_connection_id", None):
            for connection in active_connections:
                if str(connection.id) == str(database_group.reference_connection_id):
                    return connection
        if database_group.schema_profile and database_group.schema_profile.reference_connection_id:
            for connection in active_connections:
                if str(connection.id) == str(database_group.schema_profile.reference_connection_id):
                    return connection
        return sorted(active_connections, key=lambda item: item.name)[0]
