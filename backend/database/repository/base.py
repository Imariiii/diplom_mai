"""
Базовый класс для репозиториев
"""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


def get_local_now():
    """Получить текущее время в UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class BaseRepository:
    """Базовый класс для репозиториев с общими методами"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = async_sessionmaker(bind=self.engine, expire_on_commit=False)
    
    async def get_session(self) -> AsyncSession:
        """Получить новую сессию БД"""
        return self.SessionLocal()
