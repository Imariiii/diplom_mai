"""
Базовый класс для репозиториев
"""
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def get_local_now():
    """Получить текущее время в UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class BaseRepository:
    """Базовый класс для репозиториев с общими методами"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
    
    def get_session(self) -> Session:
        """Получить новую сессию БД"""
        return self.SessionLocal()