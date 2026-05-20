"""
ConnectionRepository для управления подключениями к тестируемым БД
"""
import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.database.models import Base, DatabaseConnectionConfig, DatabaseGroup
from backend.database.repository.base import BaseRepository, get_local_now
from backend.core.crypto import encrypt_password, decrypt_password


class ConnectionRepository(BaseRepository):
    """Репозиторий для управления подключениями к БД"""

    def _with_relations_query(self):
        """Базовый запрос подключения с предзагруженными связями."""
        return (
            select(DatabaseConnectionConfig)
            .options(
                joinedload(DatabaseConnectionConfig.schema_profile),
                joinedload(DatabaseConnectionConfig.database_group).joinedload(
                    DatabaseGroup.schema_profile
                ),
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

    async def _get_database_group(self, session, database_group_id: Optional[str]):
        """Получить database_group вместе с её schema_profile."""
        logical_db_uuid = self._parse_uuid(database_group_id)
        if logical_db_uuid is None:
            return None

        result = await session.execute(
            select(DatabaseGroup)
            .options(joinedload(DatabaseGroup.schema_profile))
            .where(DatabaseGroup.id == logical_db_uuid)
        )
        return result.unique().scalar_one_or_none()

    async def init_db(self):
        """Создать все таблицы"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_connection(
        self,
        name: str,
        dbms_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        group: str = 'default',
        database_group_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> DatabaseConnectionConfig:
        """
        Создать новое подключение

        Args:
            name: Уникальное имя подключения
            dbms_type: Тип СУБД (mysql/postgresql)
            host: Хост
            port: Порт
            user: Пользователь
            password: Пароль (в открытом виде, будет зашифрован)
            database: Имя базы данных
            group: Группа подключений
            database_group_id: ID группы баз данных
            extra_params: Дополнительные параметры

        Returns:
            Созданный объект подключения
        """
        encrypted_password = encrypt_password(password)

        created_id: Optional[str] = None
        async with self.SessionLocal() as session:
            logical_db = await self._get_database_group(session, database_group_id)
            config = DatabaseConnectionConfig(
                id=uuid.uuid4(),
                name=name,
                dbms_type=dbms_type,
                host=host,
                port=port,
                user=user,
                password_encrypted=encrypted_password,
                database=database,
                group=group,
                database_group_id=logical_db.id if logical_db else self._parse_uuid(database_group_id),
                schema_profile_id=None,
                detected_profile_name=(
                    logical_db.schema_profile.name
                    if logical_db and logical_db.schema_profile
                    else None
                ),
                profile_source='pending_review' if logical_db and logical_db.schema_profile_id else 'manual',
                extra_params=extra_params or {},
            )
            session.add(config)
            await session.commit()
            await session.refresh(config)
            created_id = str(config.id)

        return await self.get_connection_by_id(created_id)

    async def get_connection_by_id(self, connection_id: str) -> Optional[DatabaseConnectionConfig]:
        """Получить подключение по ID"""
        try:
            connection_uuid = uuid.UUID(connection_id)
        except (ValueError, TypeError, AttributeError):
            return None

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_relations_query().where(
                    DatabaseConnectionConfig.id == connection_uuid
                )
            )
            return result.scalar_one_or_none()

    async def get_connection_by_name(self, name: str) -> Optional[DatabaseConnectionConfig]:
        """Получить подключение по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_relations_query().where(
                    DatabaseConnectionConfig.name == name
                )
            )
            return result.scalar_one_or_none()

    async def get_all_connections(self, group: Optional[str] = None) -> List[DatabaseConnectionConfig]:
        """
        Получить все подключения

        Args:
            group: Фильтр по группе (опционально)

        Returns:
            Список подключений
        """
        async with self.SessionLocal() as session:
            query = (
                self._with_relations_query()
                .order_by(DatabaseConnectionConfig.name)
            )
            if group:
                query = query.where(DatabaseConnectionConfig.group == group)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_active_connections(self, group: Optional[str] = None) -> List[DatabaseConnectionConfig]:
        """
        Получить только активные подключения

        Args:
            group: Фильтр по группе (опционально)

        Returns:
            Список активных подключений
        """
        async with self.SessionLocal() as session:
            query = (
                self._with_relations_query()
                .where(DatabaseConnectionConfig.is_active == 't')
                .order_by(DatabaseConnectionConfig.name)
            )
            if group:
                query = query.where(DatabaseConnectionConfig.group == group)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_connection(
        self,
        connection_id: str,
        name: Optional[str] = None,
        dbms_type: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        group: Optional[str] = None,
        database_group_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        schema_profile_id: Optional[str] = None,
        detected_profile_name: Optional[str] = None,
        profile_confidence: Optional[float] = None,
        profile_source: Optional[str] = None,
    ) -> Optional[DatabaseConnectionConfig]:
        """
        Обновить подключение

        Args:
            connection_id: ID подключения
            Остальные параметры: поля для обновления (None = не менять)

        Returns:
            Обновлённый объект или None
        """
        updated_id: Optional[str] = None
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig).where(
                    DatabaseConnectionConfig.id == uuid.UUID(connection_id)
                )
            )
            config = result.scalar_one_or_none()
            if not config:
                return None

            target_logical_db = None
            if name is not None:
                config.name = name
            if dbms_type is not None:
                config.dbms_type = dbms_type
            if host is not None:
                config.host = host
            if port is not None:
                config.port = port
            if user is not None:
                config.user = user
            if password is not None:
                config.password_encrypted = encrypt_password(password)
            if database is not None:
                config.database = database
            if group is not None:
                config.group = group
            if database_group_id is not None:
                target_logical_db = await self._get_database_group(session, database_group_id)
                config.database_group_id = (
                    target_logical_db.id if target_logical_db else self._parse_uuid(database_group_id)
                )
                config.schema_profile_id = None
                config.detected_profile_name = (
                    target_logical_db.schema_profile.name
                    if target_logical_db and target_logical_db.schema_profile
                    else None
                )
                config.profile_source = (
                    'pending_review'
                    if target_logical_db and target_logical_db.schema_profile_id
                    else 'manual'
                )
            if is_active is not None:
                config.is_active = 't' if is_active else 'f'
            if extra_params is not None:
                config.extra_params = extra_params
            if schema_profile_id is not None:
                config.schema_profile_id = self._parse_uuid(schema_profile_id) if schema_profile_id else None
            if detected_profile_name is not None:
                config.detected_profile_name = detected_profile_name
            if profile_confidence is not None:
                config.profile_confidence = profile_confidence
            if profile_source is not None:
                config.profile_source = profile_source

            config.updated_at = get_local_now()

            await session.commit()
            await session.refresh(config)
            updated_id = str(config.id)

        return await self.get_connection_by_id(updated_id)

    async def bulk_get_connections(self, connection_ids: List[str]) -> List[DatabaseConnectionConfig]:
        """Получить набор подключений по списку id."""
        normalized_ids = []
        for connection_id in connection_ids:
            try:
                normalized_ids.append(uuid.UUID(connection_id))
            except (ValueError, TypeError, AttributeError):
                continue

        if not normalized_ids:
            return []

        async with self.SessionLocal() as session:
            result = await session.execute(
                self._with_relations_query().where(
                    DatabaseConnectionConfig.id.in_(normalized_ids)
                )
                .order_by(DatabaseConnectionConfig.name)
            )
            return list(result.scalars().all())

    async def assign_profile(
        self,
        connection_id: str,
        schema_profile_id: Optional[str],
        detected_profile_name: Optional[str] = None,
        profile_confidence: Optional[float] = None,
        profile_source: str = 'manual',
    ) -> Optional[DatabaseConnectionConfig]:
        """Назначить профилю подключения и зафиксировать источник назначения."""
        return await self.update_connection(
            connection_id=connection_id,
            schema_profile_id=schema_profile_id,
            detected_profile_name=detected_profile_name,
            profile_confidence=profile_confidence,
            profile_source=profile_source,
        )

    async def delete_connection(self, connection_id: str) -> bool:
        """
        Удалить подключение

        Args:
            connection_id: ID подключения

        Returns:
            True если удалено, False если не найдено
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig).where(
                    DatabaseConnectionConfig.id == uuid.UUID(connection_id)
                )
            )
            config = result.scalar_one_or_none()
            if not config:
                return False

            await session.delete(config)
            await session.commit()
            return True

    async def get_decrypted_connection(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить подключение с расшифрованным паролем

        Args:
            connection_id: ID подключения

        Returns:
            Словарь с параметрами подключения (пароль в открытом виде)
        """
        config = await self.get_connection_by_id(connection_id)
        if not config:
            return None

        decrypted_password = decrypt_password(config.password_encrypted)
        return config.to_connection_dict(decrypted_password)

    async def get_groups(self) -> List[str]:
        """Получить список уникальных групп подключений"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig.group).distinct().order_by(DatabaseConnectionConfig.group)
            )
            return [row[0] for row in result.all() if row[0]]
