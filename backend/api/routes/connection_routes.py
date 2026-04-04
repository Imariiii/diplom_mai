"""
API маршруты для управления подключениями к БД
"""
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.database.repository.connection_repository import ConnectionRepository
from backend.api.schemas.connection_schemas import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionListResponse,
    ConnectionGroupsResponse,
)
from backend import initialize

router = APIRouter(prefix="/api/connections", tags=["connections"])


def get_connection_repo() -> ConnectionRepository:
    """Получить ConnectionRepository (lazy инициализация)"""
    if not hasattr(initialize, 'connection_repository') or initialize.connection_repository is None:
        raise HTTPException(status_code=500, detail="ConnectionRepository не инициализирован")
    return initialize.connection_repository


def _connection_to_response(config) -> ConnectionResponse:
    """Конвертировать модель БД в Pydantic схему"""
    return ConnectionResponse(**config.to_dict())


@router.get("/", response_model=ConnectionListResponse)
async def list_connections(
    group: Optional[str] = None,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Получить список всех подключений"""
    try:
        connections = await repo.get_active_connections(group=group)
        groups = await repo.get_groups()
        return ConnectionListResponse(
            connections=[_connection_to_response(c) for c in connections],
            groups=groups,
        )
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка получения списка подключений: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка подключений: {e}")


@router.get("/groups", response_model=ConnectionGroupsResponse)
async def list_groups(
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Получить список групп подключений"""
    try:
        groups = await repo.get_groups()
        return ConnectionGroupsResponse(groups=groups)
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка получения групп: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения групп: {e}")


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Получить подключение по ID"""
    try:
        config = await repo.get_connection_by_id(connection_id)
        if not config:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        return _connection_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка получения подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения подключения: {e}")


@router.post("/", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    data: ConnectionCreateRequest,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Создать новое подключение"""
    try:
        existing = await repo.get_connection_by_name(data.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Подключение с именем '{data.name}' уже существует")

        config = await repo.create_connection(
            name=data.name,
            dbms_type=data.dbms_type,
            host=data.host,
            port=data.port,
            user=data.user,
            password=data.password,
            database=data.database,
            group=data.group or 'default',
            extra_params=data.extra_params,
        )
        return _connection_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка создания подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания подключения: {e}")


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    data: ConnectionUpdateRequest,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Обновить подключение"""
    try:
        config = await repo.update_connection(
            connection_id=connection_id,
            name=data.name,
            dbms_type=data.dbms_type,
            host=data.host,
            port=data.port,
            user=data.user,
            password=data.password,
            database=data.database,
            group=data.group,
            is_active=data.is_active,
            extra_params=data.extra_params,
        )
        if not config:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        return _connection_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка обновления подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления подключения: {e}")


@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Удалить подключение"""
    try:
        deleted = await repo.delete_connection(connection_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        return {"message": "Подключение удалено"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка удаления подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления подключения: {e}")


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(data: ConnectionTestRequest):
    """Протестировать подключение к БД (без сохранения)"""
    try:
        if data.dbms_type == 'mysql':
            connection_string = f"mysql+aiomysql://{data.user}:{data.password}@{data.host}:{data.port}/{data.database}"
        elif data.dbms_type == 'postgresql':
            connection_string = f"postgresql+asyncpg://{data.user}:{data.password}@{data.host}:{data.port}/{data.database}"
        else:
            raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип БД: {data.dbms_type}")

        engine = create_async_engine(connection_string, pool_pre_ping=True)
        start_time = time.time()

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            response_time_ms = (time.time() - start_time) * 1000
            return ConnectionTestResponse(
                success=True,
                message="Подключение успешно",
                response_time_ms=round(response_time_ms, 2),
            )
        finally:
            await engine.dispose()

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка тестирования подключения: {e}")
        return ConnectionTestResponse(
            success=False,
            message=f"Ошибка подключения: {e}",
            response_time_ms=None,
        )


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_saved_connection(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Протестировать сохранённое подключение"""
    try:
        decrypted = await repo.get_decrypted_connection(connection_id)
        if not decrypted:
            raise HTTPException(status_code=404, detail="Подключение не найдено")

        if decrypted['dbms_type'] == 'mysql':
            connection_string = f"mysql+aiomysql://{decrypted['user']}:{decrypted['password']}@{decrypted['host']}:{decrypted['port']}/{decrypted['database']}"
        elif decrypted['dbms_type'] == 'postgresql':
            connection_string = f"postgresql+asyncpg://{decrypted['user']}:{decrypted['password']}@{decrypted['host']}:{decrypted['port']}/{decrypted['database']}"
        else:
            raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип БД: {decrypted['dbms_type']}")

        engine = create_async_engine(connection_string, pool_pre_ping=True)
        start_time = time.time()

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            response_time_ms = (time.time() - start_time) * 1000
            return ConnectionTestResponse(
                success=True,
                message="Подключение успешно",
                response_time_ms=round(response_time_ms, 2),
            )
        finally:
            await engine.dispose()

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка тестирования подключения: {e}")
        return ConnectionTestResponse(
            success=False,
            message=f"Ошибка подключения: {e}",
            response_time_ms=None,
        )
