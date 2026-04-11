"""
API маршруты для управления подключениями к БД
"""
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.database.repository.connection_repository import ConnectionRepository
from backend.database.dialects import get_dialect, is_registered_dbms_type
from backend.database.logical_database_provisioner import LogicalDatabaseProvisioner
from backend.api.schemas.connection_schemas import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionListResponse,
    ConnectionGroupsResponse,
    ConnectionSchemaResponse,
    SchemaProfileSummaryResponse,
)
from backend.api.schemas.profile_schemas import ConnectionProfileAssignRequest
from backend.core.docker import resolve_host
from backend import initialize

router = APIRouter(prefix="/api/connections", tags=["connections"])


def get_connection_repo() -> ConnectionRepository:
    """Получить ConnectionRepository (lazy инициализация)"""
    if not hasattr(initialize, 'connection_repository') or initialize.connection_repository is None:
        raise HTTPException(status_code=500, detail="ConnectionRepository не инициализирован")
    return initialize.connection_repository


def get_profile_repo():
    """Получить репозиторий профилей схемы."""
    if not hasattr(initialize, 'profile_repository') or initialize.profile_repository is None:
        raise HTTPException(status_code=500, detail="ProfileRepository не инициализирован")
    return initialize.profile_repository


def get_bundle_repo():
    """Получить репозиторий SQL bundle'ов."""
    if not hasattr(initialize, 'scenario_bundle_repository') or initialize.scenario_bundle_repository is None:
        raise HTTPException(status_code=500, detail="ScenarioBundleRepository не инициализирован")
    return initialize.scenario_bundle_repository


def get_logical_db_repo():
    """Получить репозиторий logical database."""
    if not hasattr(initialize, 'logical_database_repository') or initialize.logical_database_repository is None:
        raise HTTPException(status_code=500, detail="LogicalDatabaseRepository не инициализирован")
    return initialize.logical_database_repository


def get_logical_db_provisioner() -> LogicalDatabaseProvisioner:
    """Собрать provisioner для auto profile / auto bundle generation."""
    return LogicalDatabaseProvisioner(
        connection_repository=get_connection_repo(),
        logical_database_repository=get_logical_db_repo(),
        profile_repository=get_profile_repo(),
        bundle_repository=get_bundle_repo(),
    )


def _connection_to_response(config) -> ConnectionResponse:
    """Конвертировать модель БД в Pydantic схему"""
    return ConnectionResponse(**config.to_dict())


def _validate_dbms_type(dbms_type: Optional[str]) -> None:
    """Проверить, что тип СУБД поддерживается проектом."""
    if dbms_type and not is_registered_dbms_type(dbms_type):
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип БД: {dbms_type}")


def _build_connection_string(
    dbms_type: str,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> str:
    """Построить строку подключения через зарегистрированный диалект."""
    dialect = get_dialect(dbms_type)
    return dialect.get_connection_url(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


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


@router.get("/{connection_id}/schema", response_model=ConnectionSchemaResponse)
async def get_connection_schema(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Получить preview схемы и предложенный профиль подключённой БД."""
    try:
        config = await repo.get_connection_by_id(connection_id)
        if not config:
            raise HTTPException(status_code=404, detail="Подключение не найдено")

        from backend.database.scenario_generator import ScenarioGenerator
        from backend.database.schema_profile_resolver import SchemaProfileResolver

        generator = ScenarioGenerator(
            connection_repo=repo,
        )
        resolver = SchemaProfileResolver(
            connection_repo=repo,
            profile_repository=get_profile_repo(),
        )
        preview = await generator.build_generation_preview(connection_id)
        suggestion = await resolver.suggest_profile(
            await resolver.schema_analyzer.analyze_connection(connection_id)
        )
        current_profile = (
            SchemaProfileSummaryResponse(**config.schema_profile.to_dict())
            if getattr(config, "schema_profile", None) else None
        )
        preview["current_profile"] = current_profile.model_dump() if current_profile else None
        preview["suggested_profile"] = suggestion
        return ConnectionSchemaResponse(**preview)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка чтения схемы подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения схемы подключения: {e}")


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
        _validate_dbms_type(data.dbms_type)
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
            logical_database_id=data.logical_database_id,
            extra_params=data.extra_params,
        )
        if data.logical_database_id:
            try:
                await get_logical_db_provisioner().ensure_logical_database_ready(
                    logical_database_id=data.logical_database_id,
                    reference_connection_id=str(config.id),
                )
                refreshed = await repo.get_connection_by_id(str(config.id))
                if refreshed:
                    config = refreshed
            except Exception as provision_error:
                print(
                    "[CONNECTIONS] Предупреждение: auto-provision logical database не выполнен: "
                    f"{provision_error}"
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
        _validate_dbms_type(data.dbms_type)
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
            logical_database_id=data.logical_database_id,
            is_active=data.is_active,
            extra_params=data.extra_params,
        )
        if not config:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        target_logical_database_id = (
            data.logical_database_id
            if data.logical_database_id is not None
            else (str(config.logical_database_id) if config.logical_database_id else None)
        )
        if target_logical_database_id:
            try:
                await get_logical_db_provisioner().ensure_logical_database_ready(
                    logical_database_id=target_logical_database_id,
                    reference_connection_id=str(config.id),
                )
                refreshed = await repo.get_connection_by_id(connection_id)
                if refreshed:
                    config = refreshed
            except Exception as provision_error:
                print(
                    "[CONNECTIONS] Предупреждение: auto-provision logical database не выполнен: "
                    f"{provision_error}"
                )
        return _connection_to_response(config)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка обновления подключения: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления подключения: {e}")


@router.put("/{connection_id}/profile", response_model=ConnectionResponse)
async def assign_connection_profile(
    connection_id: str,
    data: ConnectionProfileAssignRequest,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Подтвердить или переопределить профиль схемы для подключения."""
    try:
        config = await repo.get_connection_by_id(connection_id)
        if not config:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        if config.logical_database_id:
            logical_database_name = (
                config.logical_database.name if getattr(config, "logical_database", None) else "logical database"
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Подключение входит в logical database '{logical_database_name}'. "
                    "Назначайте schema_profile на уровне logical database."
                ),
            )

        profile_repo = get_profile_repo()
        profile = None

        if data.schema_profile_id:
            profile = await profile_repo.get_profile_by_id(data.schema_profile_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Профиль схемы не найден")
        elif data.profile_name:
            profile = await profile_repo.get_profile_by_name(data.profile_name)
            if not profile:
                profile = await profile_repo.create_profile(
                    name=data.profile_name,
                    description=data.description,
                    reference_connection_id=data.reference_connection_id,
                    is_builtin=False,
                )
        else:
            raise HTTPException(status_code=400, detail="Нужно указать schema_profile_id или profile_name")

        reference_connection_id = data.reference_connection_id or (
            str(profile.reference_connection_id) if profile.reference_connection_id else None
        )
        if reference_connection_id != (str(profile.reference_connection_id) if profile.reference_connection_id else None):
            await profile_repo.update_profile(
                profile_id=str(profile.id),
                description=data.description if data.description is not None else profile.description,
                reference_connection_id=reference_connection_id,
            )

        updated = await repo.assign_profile(
            connection_id=connection_id,
            schema_profile_id=str(profile.id),
            detected_profile_name=profile.name,
            profile_source=data.profile_source,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Подключение не найдено")
        refreshed = await repo.get_connection_by_id(connection_id)
        return _connection_to_response(refreshed)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS] Ошибка назначения профиля: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка назначения профиля: {e}")


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
        host = resolve_host(data.host)
        _validate_dbms_type(data.dbms_type)
        connection_string = _build_connection_string(
            dbms_type=data.dbms_type,
            host=host,
            port=data.port,
            user=data.user,
            password=data.password,
            database=data.database,
        )

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

        host = resolve_host(decrypted['host'])
        _validate_dbms_type(decrypted["dbms_type"])
        connection_string = _build_connection_string(
            dbms_type=decrypted["dbms_type"],
            host=host,
            port=decrypted["port"],
            user=decrypted["user"],
            password=decrypted["password"],
            database=decrypted["database"],
        )

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
