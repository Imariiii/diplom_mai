"""
Модуль для подключения к различным СУБД
Рефакторинг: динамическое управление подключениями через ConnectionRepository
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from typing import Dict, Optional, List, Any
import asyncio

from backend.core.config import settings
from backend.core.docker import resolve_host


class DatabaseConnection:
    """Класс для управления подключениями к базам данных"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.engines: Dict[str, AsyncEngine] = {}
        self._pool_sizes: Dict[str, int] = {}
        self._connection_configs: Dict[str, Dict[str, Any]] = {}
        self._connection_repo = None
        self._connections_loaded = False
        self._loading_lock: Optional[asyncio.Lock] = None

    def _resolve_connection_key(self, connection_key: str) -> str:
        """Разрешить shorthand ключ подключения в явный ID"""
        if connection_key in self._connection_configs:
            return connection_key

        if connection_key in {"mysql", "postgresql"}:
            matches = [
                key for key, config in self._connection_configs.items()
                if config.get("dbms_type") == connection_key
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    f"Найдено несколько активных подключений типа {connection_key}. "
                    f"Используйте явный connection_id."
                )

        return connection_key

    def get_dbms_type(self, connection_key: str) -> str:
        """Получить тип СУБД для ключа подключения"""
        connection_key = self._resolve_connection_key(connection_key)
        if connection_key in self._connection_configs:
            return self._connection_configs[connection_key].get('dbms_type', connection_key)
        return connection_key

    def get_connection_name(self, connection_key: str) -> str:
        """Получить отображаемое имя подключения"""
        connection_key = self._resolve_connection_key(connection_key)
        if connection_key in self._connection_configs:
            return self._connection_configs[connection_key].get('name', connection_key)
        return connection_key
    
    def set_connection_repository(self, repo):
        """Установить ConnectionRepository для динамического управления подключениями"""
        self._connection_repo = repo
    
    async def _ensure_connections_loaded(self):
        """Ленивая загрузка подключений из БД при первом async-вызове"""
        if self._connections_loaded:
            return
        
        if self._loading_lock is None:
            self._loading_lock = asyncio.Lock()
        
        async with self._loading_lock:
            if self._connections_loaded:
                return
            
            if not self._connection_repo:
                print("[DB_CONNECTION] ConnectionRepository не установлен")
                self._connections_loaded = True
                return
            
            try:
                connections = await self._connection_repo.get_active_connections()
                for conn_config in connections:
                    decrypted = await self._connection_repo.get_decrypted_connection(str(conn_config.id))
                    if decrypted:
                        self._connection_configs[str(conn_config.id)] = decrypted
                        print(f"[DB_CONNECTION] Загружено подключение: {conn_config.name} ({conn_config.dbms_type})")
                self._connections_loaded = True
            except Exception as e:
                print(f"[DB_CONNECTION] Ошибка загрузки подключений из БД: {e}")
                self._connections_loaded = True

    async def ensure_connection_config(self, connection_key: str) -> Dict[str, Any]:
        """Гарантированно загрузить конфиг конкретного подключения"""
        await self._ensure_connections_loaded()

        try:
            resolved_key = self._resolve_connection_key(connection_key)
        except ValueError:
            resolved_key = connection_key

        if resolved_key in self._connection_configs:
            return self._connection_configs[resolved_key]

        if not self._connection_repo:
            raise ValueError(
                f"Подключение '{connection_key}' не найдено. "
                f"Создайте его через UI/API или передайте явный connection_id."
            )

        decrypted = await self._connection_repo.get_decrypted_connection(connection_key)
        if not decrypted:
            raise ValueError(
                f"Подключение '{connection_key}' не найдено. "
                f"Создайте его через UI/API или передайте явный connection_id."
            )

        self._connection_configs[connection_key] = decrypted
        return decrypted
    
    def get_connection_string(self, connection_key: str) -> str:
        """Формирование строки подключения"""
        connection_key = self._resolve_connection_key(connection_key)
        dbms_type = self.get_dbms_type(connection_key)

        if connection_key in self._connection_configs:
            conn = self._connection_configs[connection_key]
            host = resolve_host(conn['host'])
            if dbms_type == 'mysql':
                return (
                    f"mysql+aiomysql://{conn['user']}:{conn['password']}"
                    f"@{host}:{conn['port']}"
                    f"/{conn['database']}"
                )
            elif dbms_type == 'postgresql':
                return (
                    f"postgresql+asyncpg://{conn['user']}:{conn['password']}"
                    f"@{host}:{conn['port']}"
                    f"/{conn['database']}"
                )
        
        raise ValueError(
            f"Подключение '{connection_key}' не найдено. "
            f"Создайте его через UI/API или передайте явный connection_id."
        )
    
    def get_engine(self, connection_key: str) -> AsyncEngine:
        """Получение или создание async engine для подключения (синхронный)"""
        connection_key = self._resolve_connection_key(connection_key)
        if connection_key not in self.engines:
            connection_string = self.get_connection_string(connection_key)
            pool_size = self._pool_sizes.get(connection_key, 5)
            self.engines[connection_key] = create_async_engine(
                connection_string,
                pool_size=pool_size,
                max_overflow=pool_size * 2,
                echo=False
            )
        return self.engines[connection_key]
    
    async def get_engine_async(self, connection_key: str) -> AsyncEngine:
        """Получение engine с предварительной загрузкой подключений из БД"""
        await self.ensure_connection_config(connection_key)
        return self.get_engine(connection_key)
    
    async def ensure_pool_size(self, connection_key: str, min_size: int):
        """Масштабировать пул соединений под количество виртуальных пользователей"""
        connection_key = self._resolve_connection_key(connection_key)
        current = self._pool_sizes.get(connection_key, 5)
        if current >= min_size:
            return
        self._pool_sizes[connection_key] = min_size
        if connection_key in self.engines:
            await self.engines[connection_key].dispose()
            del self.engines[connection_key]
    
    async def test_connection(self, db_type: str) -> bool:
        """Проверка подключения к БД"""
        try:
            await self._ensure_connections_loaded()
            engine = self.get_engine(db_type)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Ошибка подключения к {db_type}: {e}")
            return False
    
    async def close_all(self):
        """Закрытие всех подключений"""
        for engine in self.engines.values():
            await engine.dispose()
        self.engines.clear()
    
    async def recreate_engine(self, db_type: str) -> AsyncEngine:
        """
        Пересоздать engine для указанной СУБД
        Закрывает старые соединения и создаёт новый engine
        """
        if db_type in self.engines:
            await self.engines[db_type].dispose()
            del self.engines[db_type]
        return self.get_engine(db_type)
    
    async def terminate_other_connections(self, engine: AsyncEngine, db_type: str) -> int:
        """
        Завершить другие активные соединения с БД
        
        Returns:
            Количество завершённых соединений
        """
        terminated = 0
        
        db_name = None
        db_type = self.get_dbms_type(db_type)
        resolved_key = self._resolve_connection_key(db_type)
        if resolved_key in self._connection_configs:
            db_name = self._connection_configs[resolved_key].get('database')
        
        async with engine.connect() as conn:
            if db_type == 'postgresql':
                sql = """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    AND pid <> pg_backend_pid()
                    AND state != 'idle'
                """
                result = await conn.execute(text(sql))
                terminated = sum(1 for row in result if row[0])
                await conn.commit()
                
            elif db_type == 'mysql':
                result = await conn.execute(text("SHOW PROCESSLIST"))
                rows = result.fetchall()
                
                for row in rows:
                    process_id = row[0]
                    process_db = row[3] if len(row) > 3 else None
                    process_command = row[4] if len(row) > 4 else None
                    
                    if (process_command != 'Sleep' and 
                        process_db == db_name):
                        try:
                            await conn.execute(text(f"KILL {process_id}"))
                            terminated += 1
                        except:
                            pass
                
                await conn.commit()
        
        return terminated
