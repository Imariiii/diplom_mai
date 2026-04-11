"""
Репозиторий для профилей схемы и логических шаблонов сценариев.
"""
import uuid
from typing import List, Optional

from sqlalchemy import delete, select

from backend.database.logical_scenarios import LOGICAL_SCENARIO_TEMPLATES
from backend.database.models import Base, ScenarioBundle, ScenarioTemplate, SchemaProfile
from backend.database.repository.base import BaseRepository, get_local_now


class ProfileRepository(BaseRepository):
    """Работа с профилями схемы и logical scenario templates."""

    async def init_db(self):
        """Создать таблицы, если их ещё нет."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def seed_builtin_templates(self) -> None:
        """Инициализировать встроенные logical templates."""
        async with self.SessionLocal() as session:
            for template_data in LOGICAL_SCENARIO_TEMPLATES:
                existing = await session.get(ScenarioTemplate, template_data["id"])
                if existing:
                    existing.name = template_data["name"]
                    existing.description = template_data["description"]
                    existing.is_builtin = 't'
                    continue
                session.add(
                    ScenarioTemplate(
                        id=template_data["id"],
                        name=template_data["name"],
                        description=template_data["description"],
                        is_builtin='t',
                    )
                )
            await session.commit()

    async def list_profiles(self) -> List[SchemaProfile]:
        """Получить список профилей."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(SchemaProfile).order_by(SchemaProfile.name)
            )
            return list(result.scalars().all())

    async def get_profile_by_id(self, profile_id: str) -> Optional[SchemaProfile]:
        """Получить профиль по id."""
        try:
            profile_uuid = uuid.UUID(profile_id)
        except (ValueError, TypeError, AttributeError):
            return None

        async with self.SessionLocal() as session:
            result = await session.execute(
                select(SchemaProfile).where(SchemaProfile.id == profile_uuid)
            )
            return result.scalar_one_or_none()

    async def get_profile_by_name(self, name: str) -> Optional[SchemaProfile]:
        """Получить профиль по machine name."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(SchemaProfile).where(SchemaProfile.name == name)
            )
            return result.scalar_one_or_none()

    async def create_profile(
        self,
        name: str,
        description: Optional[str] = None,
        detection_mode: str = "hybrid",
        reference_connection_id: Optional[str] = None,
        is_builtin: bool = False,
    ) -> SchemaProfile:
        """Создать новый профиль схемы."""
        async with self.SessionLocal() as session:
            profile = SchemaProfile(
                id=uuid.uuid4(),
                name=name,
                description=description,
                detection_mode=detection_mode,
                reference_connection_id=uuid.UUID(reference_connection_id) if reference_connection_id else None,
                is_builtin='t' if is_builtin else 'f',
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            return profile

    async def update_profile(
        self,
        profile_id: str,
        description: Optional[str] = None,
        reference_connection_id: Optional[str] = None,
    ) -> Optional[SchemaProfile]:
        """Обновить профиль."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(SchemaProfile).where(SchemaProfile.id == uuid.UUID(profile_id))
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return None

            if description is not None:
                profile.description = description
            if reference_connection_id is not None:
                profile.reference_connection_id = uuid.UUID(reference_connection_id) if reference_connection_id else None
            profile.updated_at = get_local_now()
            await session.commit()
            await session.refresh(profile)
            return profile

    async def list_templates(self) -> List[ScenarioTemplate]:
        """Получить список logical templates."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioTemplate).order_by(ScenarioTemplate.is_builtin.desc(), ScenarioTemplate.name)
            )
            return list(result.scalars().all())

    async def get_template(self, template_id: str) -> Optional[ScenarioTemplate]:
        """Получить logical template по id."""
        async with self.SessionLocal() as session:
            return await session.get(ScenarioTemplate, template_id)

    async def create_template(
        self,
        template_id: str,
        name: str,
        description: Optional[str] = None,
        is_builtin: bool = False,
    ) -> ScenarioTemplate:
        """Создать новый logical template."""
        async with self.SessionLocal() as session:
            template = ScenarioTemplate(
                id=template_id,
                name=name,
                description=description,
                is_builtin='t' if is_builtin else 'f',
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            return template

    async def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[ScenarioTemplate]:
        """Обновить logical template."""
        async with self.SessionLocal() as session:
            template = await session.get(ScenarioTemplate, template_id)
            if not template:
                return None

            if name is not None:
                template.name = name
            if description is not None:
                template.description = description
            template.updated_at = get_local_now()
            await session.commit()
            await session.refresh(template)
            return template

    async def delete_template(self, template_id: str) -> bool:
        """Удалить пользовательский logical template."""
        async with self.SessionLocal() as session:
            template = await session.get(ScenarioTemplate, template_id)
            if not template or template.is_builtin == 't':
                return False
            await session.execute(
                delete(ScenarioBundle).where(ScenarioBundle.scenario_template_id == template_id)
            )
            await session.execute(
                delete(ScenarioTemplate).where(ScenarioTemplate.id == template_id)
            )
            await session.commit()
            return True
