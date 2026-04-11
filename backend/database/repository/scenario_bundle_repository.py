"""
Репозиторий для profile-centric SQL bundle'ов.
"""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from backend.database.models import (
    Base,
    ScenarioBundle,
    ScenarioBundleIndex,
    ScenarioBundleParam,
    ScenarioBundleQuery,
)
from backend.database.repository.base import BaseRepository, get_local_now


class ScenarioBundleRepository(BaseRepository):
    """Работа с variant-based SQL bundles для профилей."""

    def _bundle_options(self):
        return (
            joinedload(ScenarioBundle.schema_profile),
            joinedload(ScenarioBundle.scenario_template),
            joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
            joinedload(ScenarioBundle.indexes),
        )

    async def init_db(self):
        """Создать таблицы, если их ещё нет."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_bundle(self, bundle_id: str) -> Optional[ScenarioBundle]:
        """Получить bundle variant по id."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioBundle)
                .options(*self._bundle_options())
                .where(ScenarioBundle.id == uuid.UUID(bundle_id))
            )
            return result.unique().scalar_one_or_none()

    async def get_bundle_for_profile_template(
        self,
        schema_profile_id: str,
        scenario_template_id: str,
        bundle_id: Optional[str] = None,
    ) -> Optional[ScenarioBundle]:
        """Получить bundle для пары профиль + template.

        Если `bundle_id` не задан, возвращается активный variant.
        """
        async with self.SessionLocal() as session:
            query = (
                select(ScenarioBundle)
                .options(*self._bundle_options())
                .where(
                    ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id),
                    ScenarioBundle.scenario_template_id == scenario_template_id,
                )
            )
            if bundle_id:
                query = query.where(ScenarioBundle.id == uuid.UUID(bundle_id))
            else:
                query = query.where(ScenarioBundle.is_active == 't')
            result = await session.execute(query)
            return result.unique().scalar_one_or_none()

    async def list_bundles(
        self,
        schema_profile_id: Optional[str] = None,
        scenario_template_id: Optional[str] = None,
        active_only: Optional[bool] = None,
    ) -> List[ScenarioBundle]:
        """Получить список bundle variants."""
        async with self.SessionLocal() as session:
            query = select(ScenarioBundle).options(*self._bundle_options())
            if schema_profile_id:
                query = query.where(ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id))
            if scenario_template_id:
                query = query.where(ScenarioBundle.scenario_template_id == scenario_template_id)
            if active_only is True:
                query = query.where(ScenarioBundle.is_active == 't')
            elif active_only is False:
                query = query.where(ScenarioBundle.is_active == 'f')
            query = query.order_by(
                ScenarioBundle.scenario_template_id,
                ScenarioBundle.is_active.desc(),
                ScenarioBundle.is_builtin.desc(),
                ScenarioBundle.name,
            )
            result = await session.execute(query)
            return list(result.unique().scalars().all())

    async def create_bundle_variant(
        self,
        schema_profile_id: str,
        scenario_template_id: str,
        name: str,
        description: Optional[str],
        generation_source: str,
        generated_from_connection_id: Optional[str],
        queries: List[Dict[str, Any]],
        indexes: Optional[List[Dict[str, Any]]] = None,
        is_active: bool = False,
        is_builtin: bool = False,
    ) -> ScenarioBundle:
        """Создать новый bundle variant."""
        async with self.SessionLocal() as session:
            should_activate = is_active or not await self._has_active_bundle(
                session,
                schema_profile_id,
                scenario_template_id,
            )
            if should_activate:
                await self._deactivate_active_bundles(session, schema_profile_id, scenario_template_id)

            bundle = ScenarioBundle(
                id=uuid.uuid4(),
                schema_profile_id=uuid.UUID(schema_profile_id),
                scenario_template_id=scenario_template_id,
                name=name,
                description=description,
                generation_source=generation_source,
                generated_from_connection_id=(
                    uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
                ),
                is_active='t' if should_activate else 'f',
                is_builtin='t' if is_builtin else 'f',
            )
            session.add(bundle)
            await session.flush()
            await self._replace_bundle_contents(session, bundle, queries, indexes or [])
            await session.commit()
            return await self.get_bundle(str(bundle.id))

    async def update_bundle_variant(
        self,
        bundle_id: str,
        name: str,
        description: Optional[str],
        generation_source: str,
        generated_from_connection_id: Optional[str],
        queries: List[Dict[str, Any]],
        indexes: Optional[List[Dict[str, Any]]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ScenarioBundle]:
        """Полностью обновить bundle variant."""
        async with self.SessionLocal() as session:
            bundle = await self._get_bundle_for_update(session, bundle_id)
            if not bundle:
                return None

            if bundle.is_active == 't' and is_active is False:
                raise ValueError("Нельзя снять active-флаг без предварительной активации другого variant")

            target_active = (bundle.is_active == 't') if is_active is None else is_active
            if target_active:
                await self._deactivate_active_bundles(
                    session,
                    str(bundle.schema_profile_id),
                    bundle.scenario_template_id,
                    exclude_bundle_id=str(bundle.id),
                )

            bundle.name = name
            bundle.description = description
            bundle.generation_source = generation_source
            bundle.generated_from_connection_id = (
                uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
            )
            bundle.is_active = 't' if target_active else 'f'
            bundle.updated_at = get_local_now()

            await self._replace_bundle_contents(session, bundle, queries, indexes or [])
            await session.commit()
            return await self.get_bundle(str(bundle.id))

    async def clone_bundle(
        self,
        bundle_id: str,
        new_name: str,
    ) -> Optional[ScenarioBundle]:
        """Клонировать bundle в новый пользовательский variant."""
        source_bundle = await self.get_bundle(bundle_id)
        if not source_bundle:
            return None
        source_payload = source_bundle.to_dict()
        return await self.create_bundle_variant(
            schema_profile_id=source_payload["schema_profile_id"],
            scenario_template_id=source_payload["scenario_template_id"],
            name=new_name,
            description=source_payload.get("description"),
            generation_source="manual_variant",
            generated_from_connection_id=source_payload.get("generated_from_connection_id"),
            queries=source_payload.get("queries", []),
            indexes=source_payload.get("indexes", []),
            is_active=False,
            is_builtin=False,
        )

    async def set_active_bundle(self, bundle_id: str) -> Optional[ScenarioBundle]:
        """Сделать variant активным для его пары профиль + template."""
        async with self.SessionLocal() as session:
            bundle = await self._get_bundle_for_update(session, bundle_id)
            if not bundle:
                return None
            await self._deactivate_active_bundles(
                session,
                str(bundle.schema_profile_id),
                bundle.scenario_template_id,
                exclude_bundle_id=str(bundle.id),
            )
            bundle.is_active = 't'
            bundle.updated_at = get_local_now()
            await session.commit()
            return await self.get_bundle(str(bundle.id))

    async def delete_bundle(self, bundle_id: str) -> bool:
        """Удалить пользовательский неактивный variant."""
        async with self.SessionLocal() as session:
            bundle = await self._get_bundle_for_update(session, bundle_id)
            if not bundle:
                return False
            if bundle.is_builtin == 't':
                raise ValueError("Нельзя удалить системный bundle")
            if bundle.is_active == 't':
                raise ValueError("Сначала активируйте другой variant, затем удалите текущий")
            await session.delete(bundle)
            await session.commit()
            return True

    async def upsert_generated_bundle(
        self,
        schema_profile_id: str,
        scenario_template_id: str,
        name: str,
        description: Optional[str],
        generation_source: str,
        generated_from_connection_id: Optional[str],
        queries: List[Dict[str, Any]],
        indexes: Optional[List[Dict[str, Any]]] = None,
    ) -> ScenarioBundle:
        """Создать или обновить системный generated bundle для profile/template."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioBundle)
                .options(
                    joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
                    joinedload(ScenarioBundle.indexes),
                )
                .where(
                    ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id),
                    ScenarioBundle.scenario_template_id == scenario_template_id,
                    ScenarioBundle.is_builtin == 't',
                )
            )
            bundle = result.unique().scalar_one_or_none()
            active_exists = await self._has_active_bundle(session, schema_profile_id, scenario_template_id)

            if bundle is None:
                bundle = ScenarioBundle(
                    id=uuid.uuid4(),
                    schema_profile_id=uuid.UUID(schema_profile_id),
                    scenario_template_id=scenario_template_id,
                    name=name,
                    description=description,
                    generation_source=generation_source,
                    generated_from_connection_id=(
                        uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
                    ),
                    is_active='f' if active_exists else 't',
                    is_builtin='t',
                )
                session.add(bundle)
                await session.flush()
            else:
                bundle.name = name
                bundle.description = description
                bundle.generation_source = generation_source
                bundle.generated_from_connection_id = (
                    uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
                )
                if bundle.is_active != 't' and not active_exists:
                    bundle.is_active = 't'
                bundle.updated_at = get_local_now()

            await self._replace_bundle_contents(session, bundle, queries, indexes or [])
            await session.commit()
            return await self.get_bundle(str(bundle.id))

    async def _get_bundle_for_update(self, session, bundle_id: str) -> Optional[ScenarioBundle]:
        result = await session.execute(
            select(ScenarioBundle)
            .options(
                joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
                joinedload(ScenarioBundle.indexes),
            )
            .where(ScenarioBundle.id == uuid.UUID(bundle_id))
        )
        return result.unique().scalar_one_or_none()

    async def _has_active_bundle(
        self,
        session,
        schema_profile_id: str,
        scenario_template_id: str,
    ) -> bool:
        result = await session.execute(
            select(ScenarioBundle.id).where(
                ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id),
                ScenarioBundle.scenario_template_id == scenario_template_id,
                ScenarioBundle.is_active == 't',
            )
        )
        return result.scalar_one_or_none() is not None

    async def _deactivate_active_bundles(
        self,
        session,
        schema_profile_id: str,
        scenario_template_id: str,
        exclude_bundle_id: Optional[str] = None,
    ) -> None:
        result = await session.execute(
            select(ScenarioBundle).where(
                ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id),
                ScenarioBundle.scenario_template_id == scenario_template_id,
                ScenarioBundle.is_active == 't',
            )
        )
        for bundle in result.scalars().all():
            if exclude_bundle_id and str(bundle.id) == exclude_bundle_id:
                continue
            bundle.is_active = 'f'
            bundle.updated_at = get_local_now()

    async def _replace_bundle_contents(
        self,
        session,
        bundle: ScenarioBundle,
        queries: List[Dict[str, Any]],
        indexes: List[Dict[str, Any]],
    ) -> None:
        await session.execute(
            delete(ScenarioBundleQuery).where(ScenarioBundleQuery.bundle_id == bundle.id)
        )
        await session.execute(
            delete(ScenarioBundleIndex).where(ScenarioBundleIndex.bundle_id == bundle.id)
        )
        await session.flush()

        for order_index, query_payload in enumerate(queries):
            query = ScenarioBundleQuery(
                id=uuid.uuid4(),
                bundle_id=bundle.id,
                sql_template=query_payload["sql_template"],
                query_type=query_payload["query_type"],
                weight=query_payload.get("weight", 1),
                order_index=query_payload.get("order_index", order_index),
                description=query_payload.get("description"),
            )
            session.add(query)
            await session.flush()

            for param_payload in query_payload.get("params", []):
                session.add(
                    ScenarioBundleParam(
                        id=uuid.uuid4(),
                        query_id=query.id,
                        param_name=param_payload["param_name"],
                        param_type=param_payload["param_type"],
                        min_value=param_payload.get("min_value"),
                        max_value=param_payload.get("max_value"),
                        string_pattern=param_payload.get("string_pattern"),
                        string_length=param_payload.get("string_length"),
                        table_ref=param_payload.get("table_ref"),
                        column_ref=param_payload.get("column_ref"),
                        current_value=param_payload.get("current_value", 0),
                        step=param_payload.get("step", 1),
                    )
                )

        for index_payload in indexes:
            session.add(
                ScenarioBundleIndex(
                    id=uuid.uuid4(),
                    bundle_id=bundle.id,
                    table_name=index_payload["table_name"],
                    column_names=index_payload["column_names"],
                    index_type=index_payload.get("index_type", "btree"),
                    index_name=index_payload.get("index_name"),
                    is_unique='t' if index_payload.get("is_unique") else 'f',
                    condition=index_payload.get("condition"),
                    description=index_payload.get("description"),
                )
            )
