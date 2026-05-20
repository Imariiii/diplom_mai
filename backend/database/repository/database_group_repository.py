"""
DatabaseGroupRepository — управление группами баз данных
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.database.models import DatabaseGroup, DatabaseConnectionConfig
from backend.database.repository.base import BaseRepository, get_local_now


class DatabaseGroupRepository(BaseRepository):
    """Репозиторий для управления группами баз данных"""

    def _with_connections_query(self):
        """Базовый запрос группы баз данных с eager-loaded подключениями."""
        return (
            select(DatabaseGroup)
            .options(
                joinedload(DatabaseGroup.schema_profile),
                joinedload(DatabaseGroup.reference_connection),
                joinedload(DatabaseGroup.connections).joinedload(
                    DatabaseConnectionConfig.schema_profile
                )
            )
        )

    @staticmethod
    def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
        """Безопасно распарсить UUID из строки."""
        if not value:
            return None
        try:
            return uuid.UUID(value)
        except (ValueError, TypeError, AttributeError):
            return None

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        schema_profile_id: Optional[str] = None,
    ) -> DatabaseGroup:
        """
        Создать новую группу баз данных

        Args:
            name: Уникальное название
            description: Описание датасета / модели данных

        Returns:
            Созданный объект DatabaseGroup
        """
        created_id: Optional[str] = None
        async with self.SessionLocal() as session:
            db = DatabaseGroup(
                id=uuid.uuid4(),
                name=name,
                description=description,
                schema_profile_id=self._parse_uuid(schema_profile_id),
            )
            session.add(db)
            await session.commit()
            await session.refresh(db)
            created_id = str(db.id)

        return await self.get_by_id(created_id)

    async def get_by_id(self, database_group_id: str) -> Optional[DatabaseGroup]:
        """Получить группу баз данных по ID"""
        try:
            db_uuid = uuid.UUID(database_group_id)
        except (ValueError, TypeError, AttributeError):
            return None

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(DatabaseGroup.id == db_uuid)
            )
            return result.unique().scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[DatabaseGroup]:
        """Получить группу баз данных по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(DatabaseGroup.name == name)
            )
            return result.unique().scalar_one_or_none()

    async def get_all(self) -> List[DatabaseGroup]:
        """Получить все группы баз данных"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().order_by(DatabaseGroup.name)
            )
            return list(result.unique().scalars().all())

    async def get_all_with_connections(self) -> List[DatabaseGroup]:
        """Получить все группы баз данных вместе с подключениями"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query()
                .order_by(DatabaseGroup.name)
            )
            return list(result.unique().scalars().all())

    async def update(
        self,
        database_group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema_profile_id: Optional[str] = None,
    ) -> Optional[DatabaseGroup]:
        """
        Обновить группу баз данных

        Args:
            database_group_id: ID группы баз данных
            name: Новое название (None — не менять)
            description: Новое описание (None — не менять)

        Returns:
            Обновлённый объект или None
        """
        updated_id: Optional[str] = None
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseGroup).where(
                    DatabaseGroup.id == uuid.UUID(database_group_id)
                )
            )
            db = result.scalar_one_or_none()
            if not db:
                return None

            if name is not None:
                db.name = name
            if description is not None:
                db.description = description
            if schema_profile_id is not None:
                db.schema_profile_id = self._parse_uuid(schema_profile_id) if schema_profile_id else None
            db.updated_at = get_local_now()

            await session.commit()
            await session.refresh(db)
            updated_id = str(db.id)

        return await self.get_by_id(updated_id)

    async def get_connections_by_database_group(
        self,
        database_group_id: str,
    ) -> List[DatabaseConnectionConfig]:
        """Получить все подключения, привязанные к группы баз данных."""
        try:
            db_uuid = uuid.UUID(database_group_id)
        except (ValueError, TypeError, AttributeError):
            return []

        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig)
                .options(
                    joinedload(DatabaseConnectionConfig.schema_profile),
                    joinedload(DatabaseConnectionConfig.database_group).joinedload(
                        DatabaseGroup.schema_profile
                    ),
                )
                .where(DatabaseConnectionConfig.database_group_id == db_uuid)
                .order_by(DatabaseConnectionConfig.name)
            )
            return list(result.scalars().all())

    async def assign_profile(
        self,
        database_group_id: str,
        schema_profile_id: Optional[str],
        schema_profile_name: Optional[str] = None,
        profile_source: str = "inherited",
        reference_connection_id: Optional[str] = None,
        profile_status: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        compatibility_report: Optional[Dict[str, Any]] = None,
    ) -> Optional[DatabaseGroup]:
        """Назначить профиль группы баз данных и каскадно синхронизировать её подключения."""
        logical_db_uuid = self._parse_uuid(database_group_id)
        if logical_db_uuid is None:
            return None

        profile_uuid = self._parse_uuid(schema_profile_id) if schema_profile_id else None
        updated_id: Optional[str] = None

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(DatabaseGroup.id == logical_db_uuid)
            )
            db = result.unique().scalar_one_or_none()
            if not db:
                return None

            db.schema_profile_id = profile_uuid
            if reference_connection_id is not None:
                db.reference_connection_id = self._parse_uuid(reference_connection_id)
            if profile_status is not None:
                db.profile_status = profile_status
            if compatibility_status is not None:
                db.compatibility_status = compatibility_status
            if compatibility_report is not None:
                db.compatibility_report = compatibility_report
                db.validated_at = datetime.now(timezone.utc)
            db.updated_at = get_local_now()

            for connection in db.connections or []:
                connection.schema_profile_id = profile_uuid
                connection.updated_at = get_local_now()
                connection.profile_source = profile_source
                if schema_profile_name is not None:
                    connection.detected_profile_name = schema_profile_name

            await session.commit()
            updated_id = str(db.id)

        return await self.get_by_id(updated_id)

    async def update_profile_state(
        self,
        database_group_id: str,
        profile_status: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        compatibility_report: Optional[Dict[str, Any]] = None,
        reference_connection_id: Optional[str] = None,
    ) -> Optional[DatabaseGroup]:
        """Обновить статус профиля/совместимости database group без каскада на подключения."""
        logical_db_uuid = self._parse_uuid(database_group_id)
        if logical_db_uuid is None:
            return None

        updated_id: Optional[str] = None
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseGroup).where(DatabaseGroup.id == logical_db_uuid)
            )
            db = result.scalar_one_or_none()
            if not db:
                return None

            if profile_status is not None:
                db.profile_status = profile_status
            if compatibility_status is not None:
                db.compatibility_status = compatibility_status
            if compatibility_report is not None:
                db.compatibility_report = compatibility_report
                db.validated_at = datetime.now(timezone.utc)
            if reference_connection_id is not None:
                db.reference_connection_id = self._parse_uuid(reference_connection_id)
            db.updated_at = get_local_now()

            await session.commit()
            updated_id = str(db.id)

        return await self.get_by_id(updated_id)

    async def set_reference_connection(
        self,
        database_group_id: str,
        reference_connection_id: Optional[str],
    ) -> Optional[DatabaseGroup]:
        """Назначить эталонное подключение database group."""
        return await self.update_profile_state(
            database_group_id=database_group_id,
            reference_connection_id=reference_connection_id or "",
        )

    async def delete(self, database_group_id: str) -> bool:
        """
        Удалить группу баз данных (подключения получают database_group_id = NULL)

        Args:
            database_group_id: ID группы баз данных

        Returns:
            True если удалено, False если не найдено
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseGroup).where(
                    DatabaseGroup.id == uuid.UUID(database_group_id)
                )
            )
            db = result.scalar_one_or_none()
            if not db:
                return False

            await session.delete(db)
            await session.commit()
            return True
