"""
Разрешение logical scenario template в конкретный SQL bundle.
"""
from typing import Any, Dict, List, Optional

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.repository.scenario_bundle_repository import ScenarioBundleRepository


class ScenarioBundleResolver:
    """Подбирает канонический bundle по профилю выбранных БД."""

    def __init__(
        self,
        connection_repository: ConnectionRepository,
        bundle_repository: ScenarioBundleRepository,
    ):
        self.connection_repository = connection_repository
        self.bundle_repository = bundle_repository

    async def resolve_for_connections(
        self,
        connection_ids: List[str],
        scenario_template_id: Optional[str] = None,
        bundle_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Разрешить template/bundle в конкретный SQL bundle и проверить совместимость профилей."""
        if not connection_ids:
            raise ValueError("Не выбраны подключения для теста")
        if not scenario_template_id and not bundle_id:
            raise ValueError("Не указан scenario_template_id или bundle_id")

        connections = await self.connection_repository.bulk_get_connections(connection_ids)
        if len(connections) != len(connection_ids):
            raise ValueError("Не удалось загрузить все выбранные подключения")

        logical_database_ids = {
            str(connection.logical_database_id)
            for connection in connections
            if connection.logical_database_id
        }
        if logical_database_ids:
            if len(logical_database_ids) != 1 or any(not connection.logical_database_id for connection in connections):
                raise ValueError(
                    "Нельзя запускать тест сразу для нескольких logical database "
                    "или смешивать их с подключениями без logical database"
                )

            logical_database = connections[0].logical_database
            if not logical_database or not logical_database.schema_profile_id:
                raise ValueError(
                    f"Для logical database '{connections[0].logical_database.name if connections[0].logical_database else logical_database_ids.pop()}' "
                    "не назначен schema_profile"
                )

            schema_profile_id = str(logical_database.schema_profile_id)
            inconsistent_connections = [
                connection.name
                for connection in connections
                if connection.schema_profile_id and str(connection.schema_profile_id) != schema_profile_id
            ]
            if inconsistent_connections:
                raise ValueError(
                    "Для части подключений logical database не синхронизирован schema_profile: "
                    + ", ".join(inconsistent_connections)
                )
        else:
            profile_ids = {str(connection.schema_profile_id) for connection in connections if connection.schema_profile_id}
            missing_profile_connections = [connection.name for connection in connections if not connection.schema_profile_id]
            if missing_profile_connections:
                raise ValueError(
                    "Для части подключений не назначен schema_profile: "
                    + ", ".join(missing_profile_connections)
                )

            if len(profile_ids) != 1:
                profile_names = sorted({
                    connection.schema_profile.name if connection.schema_profile else "unknown"
                    for connection in connections
                })
                raise ValueError(
                    "Нельзя запускать тест сразу для разных профилей модели данных: "
                    + ", ".join(profile_names)
                )

            schema_profile_id = next(iter(profile_ids))

        bundle = None
        if bundle_id:
            bundle = await self.bundle_repository.get_bundle(bundle_id)
            if not bundle:
                raise ValueError(f"Bundle '{bundle_id}' не найден")
            if str(bundle.schema_profile_id) != schema_profile_id:
                raise ValueError("Выбранный bundle не соответствует profile выбранных подключений")
            if scenario_template_id and bundle.scenario_template_id != scenario_template_id:
                raise ValueError("Bundle не соответствует выбранному logical template")
        elif scenario_template_id:
            bundle = await self.bundle_repository.get_bundle_for_profile_template(
                schema_profile_id=schema_profile_id,
                scenario_template_id=scenario_template_id,
            )
        if not bundle:
            profile_name = connections[0].schema_profile.name if connections[0].schema_profile else schema_profile_id
            raise ValueError(
                f"Для профиля '{profile_name}' не найден active bundle сценария '{scenario_template_id}'"
            )

        return {
            "schema_profile_id": schema_profile_id,
            "schema_profile_name": bundle.schema_profile.name if bundle.schema_profile else None,
            "scenario_template_id": bundle.scenario_template_id,
            "bundle": self.bundle_to_execution_dict(bundle.to_dict()),
        }

    def bundle_to_execution_dict(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Привести bundle к формату, совместимому с LoadTester.run_scenario_test."""
        return {
            "id": bundle["id"],
            "name": bundle["name"],
            "description": bundle.get("description"),
            "scenario_type": bundle["scenario_template_id"],
            "queries": bundle.get("queries", []),
            "indexes": bundle.get("indexes", []),
            "schema_profile_id": bundle.get("schema_profile_id"),
            "schema_profile_name": bundle.get("schema_profile_name"),
            "scenario_template_id": bundle.get("scenario_template_id"),
            "scenario_template_name": bundle.get("scenario_template_name"),
            "generation_source": bundle.get("generation_source"),
            "is_builtin": bundle.get("is_builtin"),
        }
