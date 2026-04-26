"""
LogicalDatabaseRepository — управление логическими базами данных
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.database.models import LogicalDatabase, DatabaseConnectionConfig
from backend.database.repository.base import BaseRepository, get_local_now


class LogicalDatabaseRepository(BaseRepository):
    """Репозиторий для управления логическими базами данных"""

    def _with_connections_query(self):
        """Базовый запрос логической БД с eager-loaded подключениями."""
        return (
            select(LogicalDatabase)
            .options(
                joinedload(LogicalDatabase.schema_profile),
                joinedload(LogicalDatabase.reference_connection),
                joinedload(LogicalDatabase.connections).joinedload(
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
    ) -> LogicalDatabase:
        """
        Создать новую логическую базу данных

        Args:
            name: Уникальное название
            description: Описание датасета / модели данных

        Returns:
            Созданный объект LogicalDatabase
        """
        created_id: Optional[str] = None
        async with self.SessionLocal() as session:
            db = LogicalDatabase(
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

    async def get_by_id(self, logical_db_id: str) -> Optional[LogicalDatabase]:
        """Получить логическую БД по ID"""
        try:
            db_uuid = uuid.UUID(logical_db_id)
        except (ValueError, TypeError, AttributeError):
            return None

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(LogicalDatabase.id == db_uuid)
            )
            return result.unique().scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[LogicalDatabase]:
        """Получить логическую БД по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(LogicalDatabase.name == name)
            )
            return result.unique().scalar_one_or_none()

    async def get_all(self) -> List[LogicalDatabase]:
        """Получить все логические базы данных"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().order_by(LogicalDatabase.name)
            )
            return list(result.unique().scalars().all())

    async def get_all_with_connections(self) -> List[LogicalDatabase]:
        """Получить все логические БД вместе с подключениями"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query()
                .order_by(LogicalDatabase.name)
            )
            return list(result.unique().scalars().all())

    async def update(
        self,
        logical_db_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema_profile_id: Optional[str] = None,
    ) -> Optional[LogicalDatabase]:
        """
        Обновить логическую базу данных

        Args:
            logical_db_id: ID логической БД
            name: Новое название (None — не менять)
            description: Новое описание (None — не менять)

        Returns:
            Обновлённый объект или None
        """
        updated_id: Optional[str] = None
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(LogicalDatabase).where(
                    LogicalDatabase.id == uuid.UUID(logical_db_id)
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

    async def get_connections_by_logical_database(
        self,
        logical_db_id: str,
    ) -> List[DatabaseConnectionConfig]:
        """Получить все подключения, привязанные к логической БД."""
        try:
            db_uuid = uuid.UUID(logical_db_id)
        except (ValueError, TypeError, AttributeError):
            return []

        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig)
                .options(
                    joinedload(DatabaseConnectionConfig.schema_profile),
                    joinedload(DatabaseConnectionConfig.logical_database).joinedload(
                        LogicalDatabase.schema_profile
                    ),
                )
                .where(DatabaseConnectionConfig.logical_database_id == db_uuid)
                .order_by(DatabaseConnectionConfig.name)
            )
            return list(result.scalars().all())

    async def assign_profile(
        self,
        logical_db_id: str,
        schema_profile_id: Optional[str],
        schema_profile_name: Optional[str] = None,
        profile_source: str = "inherited",
        reference_connection_id: Optional[str] = None,
        profile_status: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        compatibility_report: Optional[Dict[str, Any]] = None,
    ) -> Optional[LogicalDatabase]:
        """Назначить профиль логической БД и каскадно синхронизировать её подключения."""
        logical_db_uuid = self._parse_uuid(logical_db_id)
        if logical_db_uuid is None:
            return None

        profile_uuid = self._parse_uuid(schema_profile_id) if schema_profile_id else None
        updated_id: Optional[str] = None

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_connections_query().where(LogicalDatabase.id == logical_db_uuid)
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
        logical_db_id: str,
        profile_status: Optional[str] = None,
        compatibility_status: Optional[str] = None,
        compatibility_report: Optional[Dict[str, Any]] = None,
        reference_connection_id: Optional[str] = None,
    ) -> Optional[LogicalDatabase]:
        """Обновить статус профиля/совместимости logical database без каскада на подключения."""
        logical_db_uuid = self._parse_uuid(logical_db_id)
        if logical_db_uuid is None:
            return None

        updated_id: Optional[str] = None
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(LogicalDatabase).where(LogicalDatabase.id == logical_db_uuid)
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
        logical_db_id: str,
        reference_connection_id: Optional[str],
    ) -> Optional[LogicalDatabase]:
        """Назначить эталонное подключение logical database."""
        return await self.update_profile_state(
            logical_db_id=logical_db_id,
            reference_connection_id=reference_connection_id or "",
        )

    async def delete(self, logical_db_id: str) -> bool:
        """
        Удалить логическую базу данных (подключения получают logical_database_id = NULL)

        Args:
            logical_db_id: ID логической БД

        Returns:
            True если удалено, False если не найдено
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(LogicalDatabase).where(
                    LogicalDatabase.id == uuid.UUID(logical_db_id)
                )
            )
            db = result.scalar_one_or_none()
            if not db:
                return False

            await session.delete(db)
            await session.commit()
            return True
