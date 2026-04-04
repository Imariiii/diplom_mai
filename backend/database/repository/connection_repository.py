"""
ConnectionRepository для управления подключениями к тестируемым БД
"""
import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from backend.database.models import Base, DatabaseConnectionConfig
from backend.database.repository.base import BaseRepository, get_local_now
from backend.core.crypto import encrypt_password, decrypt_password


class ConnectionRepository(BaseRepository):
    """Репозиторий для управления подключениями к БД"""

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
            extra_params: Дополнительные параметры

        Returns:
            Созданный объект подключения
        """
        encrypted_password = encrypt_password(password)

        async with self.SessionLocal() as session:
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
                extra_params=extra_params or {},
            )
            session.add(config)
            await session.commit()
            await session.refresh(config)
            return config

    async def get_connection_by_id(self, connection_id: str) -> Optional[DatabaseConnectionConfig]:
        """Получить подключение по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig).where(
                    DatabaseConnectionConfig.id == uuid.UUID(connection_id)
                )
            )
            return result.scalar_one_or_none()

    async def get_connection_by_name(self, name: str) -> Optional[DatabaseConnectionConfig]:
        """Получить подключение по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig).where(
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
            query = select(DatabaseConnectionConfig).order_by(DatabaseConnectionConfig.name)
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
            query = select(DatabaseConnectionConfig).where(
                DatabaseConnectionConfig.is_active == 't'
            ).order_by(DatabaseConnectionConfig.name)
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
        is_active: Optional[bool] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[DatabaseConnectionConfig]:
        """
        Обновить подключение

        Args:
            connection_id: ID подключения
            Остальные параметры: поля для обновления (None = не менять)

        Returns:
            Обновлённый объект или None
        """
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DatabaseConnectionConfig).where(
                    DatabaseConnectionConfig.id == uuid.UUID(connection_id)
                )
            )
            config = result.scalar_one_or_none()
            if not config:
                return None

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
            if is_active is not None:
                config.is_active = 't' if is_active else 'f'
            if extra_params is not None:
                config.extra_params = extra_params

            config.updated_at = get_local_now()

            await session.commit()
            await session.refresh(config)
            return config

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
