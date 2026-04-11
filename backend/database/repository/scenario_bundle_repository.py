"""
Репозиторий для profile-centric SQL bundle'ов.
"""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
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
    """Работа с каноническими наборами SQL для профилей."""

    async def init_db(self):
        """Создать таблицы, если их ещё нет."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_bundle(self, bundle_id: str) -> Optional[ScenarioBundle]:
        """Получить bundle по id."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioBundle)
                .options(
                    joinedload(ScenarioBundle.schema_profile),
                    joinedload(ScenarioBundle.scenario_template),
                    joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
                    joinedload(ScenarioBundle.indexes),
                )
                .where(ScenarioBundle.id == uuid.UUID(bundle_id))
            )
            return result.unique().scalar_one_or_none()

    async def get_bundle_for_profile_template(
        self,
        schema_profile_id: str,
        scenario_template_id: str,
    ) -> Optional[ScenarioBundle]:
        """Получить active bundle для пары профиль + template."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioBundle)
                .options(
                    joinedload(ScenarioBundle.schema_profile),
                    joinedload(ScenarioBundle.scenario_template),
                    joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
                    joinedload(ScenarioBundle.indexes),
                )
                .where(
                    ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id),
                    ScenarioBundle.scenario_template_id == scenario_template_id,
                    ScenarioBundle.is_active == 't',
                )
            )
            return result.unique().scalar_one_or_none()

    async def list_bundles(
        self,
        schema_profile_id: Optional[str] = None,
        scenario_template_id: Optional[str] = None,
    ) -> List[ScenarioBundle]:
        """Получить список bundle'ов."""
        async with self.SessionLocal() as session:
            query = select(ScenarioBundle).options(
                joinedload(ScenarioBundle.schema_profile),
                joinedload(ScenarioBundle.scenario_template),
                joinedload(ScenarioBundle.queries).joinedload(ScenarioBundleQuery.params),
                joinedload(ScenarioBundle.indexes),
            )
            if schema_profile_id:
                query = query.where(ScenarioBundle.schema_profile_id == uuid.UUID(schema_profile_id))
            if scenario_template_id:
                query = query.where(ScenarioBundle.scenario_template_id == scenario_template_id)
            query = query.order_by(ScenarioBundle.name)
            result = await session.execute(query)
            return list(result.unique().scalars().all())

    async def upsert_bundle(
        self,
        schema_profile_id: str,
        scenario_template_id: str,
        name: str,
        generation_source: str,
        generated_from_connection_id: Optional[str],
        queries: List[Dict[str, Any]],
        indexes: Optional[List[Dict[str, Any]]] = None,
    ) -> ScenarioBundle:
        """Создать или заменить bundle для профиля и logical template."""
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
                )
            )
            bundle = result.unique().scalar_one_or_none()

            if bundle is None:
                bundle = ScenarioBundle(
                    id=uuid.uuid4(),
                    schema_profile_id=uuid.UUID(schema_profile_id),
                    scenario_template_id=scenario_template_id,
                    name=name,
                    generation_source=generation_source,
                    generated_from_connection_id=(
                        uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
                    ),
                    is_active='t',
                )
                session.add(bundle)
                await session.flush()
            else:
                bundle.name = name
                bundle.generation_source = generation_source
                bundle.generated_from_connection_id = (
                    uuid.UUID(generated_from_connection_id) if generated_from_connection_id else None
                )
                bundle.is_active = 't'
                bundle.updated_at = get_local_now()
                for existing_query in list(bundle.queries):
                    await session.delete(existing_query)
                for existing_index in list(bundle.indexes):
                    await session.delete(existing_index)
                await session.flush()

            for order_index, query_payload in enumerate(queries):
                query = ScenarioBundleQuery(
                    id=uuid.uuid4(),
                    bundle_id=bundle.id,
                    sql_template=query_payload["sql_template"],
                    query_type=query_payload["query_type"],
                    weight=query_payload.get("weight", 1),
                    order_index=order_index,
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

            for index_payload in indexes or []:
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

            await session.commit()
            await session.refresh(bundle)
            return bundle
