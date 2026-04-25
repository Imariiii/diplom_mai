"""
API маршруты для управления логическими базами данных
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect

from backend import initialize
from backend.api.schemas.logical_database_schemas import (
    LogicalDatabaseBundlesGenerateResponse,
    LogicalDatabaseConnectionSummary,
    LogicalDatabaseCreateRequest,
    LogicalDatabaseDetailResponse,
    LogicalDatabaseListResponse,
    LogicalDatabaseProfileAssignRequest,
    LogicalDatabaseResponse,
    LogicalDatabaseUpdateRequest,
)
from backend.api.schemas.profile_schemas import (
    ProfileBundleGenerateRequest,
    ScenarioBundleSummaryResponse,
)
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.scenario_generator import ScenarioGenerator

router = APIRouter(prefix="/api/logical-databases", tags=["logical-databases"])


def get_logical_db_repo() -> LogicalDatabaseRepository:
    """Получить LogicalDatabaseRepository (lazy инициализация)."""
    if not hasattr(initialize, 'logical_database_repository') or initialize.logical_database_repository is None:
        raise HTTPException(status_code=500, detail="LogicalDatabaseRepository не инициализирован")
    return initialize.logical_database_repository


def get_profile_repo():
    """Получить репозиторий профилей схемы."""
    if not hasattr(initialize, 'profile_repository') or initialize.profile_repository is None:
        raise HTTPException(status_code=500, detail="ProfileRepository не инициализирован")
    return initialize.profile_repository


def get_bundle_repo():
    """Получить репозиторий bundle'ов."""
    if not hasattr(initialize, 'scenario_bundle_repository') or initialize.scenario_bundle_repository is None:
        raise HTTPException(status_code=500, detail="ScenarioBundleRepository не инициализирован")
    return initialize.scenario_bundle_repository


def get_connection_repo():
    """Получить репозиторий подключений."""
    if not hasattr(initialize, 'connection_repository') or initialize.connection_repository is None:
        raise HTTPException(status_code=500, detail="ConnectionRepository не инициализирован")
    return initialize.connection_repository


def _serialize_connections(db, connections=None):
    """Подготовить список active-подключений для ответа."""
    if connections is not None:
        conn_list = connections
    else:
        state = inspect(db)
        conn_list = [] if 'connections' in state.unloaded else (db.connections or [])
    return [
        LogicalDatabaseConnectionSummary(
            id=str(connection.id),
            name=connection.name,
            dbms_type=connection.dbms_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            group=connection.group,
            schema_profile_id=str(connection.schema_profile_id) if connection.schema_profile_id else None,
            schema_profile_name=connection.schema_profile.name if connection.schema_profile else None,
            is_active=connection.is_active == 't',
        )
        for connection in conn_list
        if connection.is_active == 't'
    ]


def _to_response(db, connections=None) -> LogicalDatabaseResponse:
    """Конвертировать logical database в базовый ответ."""
    return LogicalDatabaseResponse(
        id=str(db.id),
        name=db.name,
        description=db.description,
        schema_profile_id=str(db.schema_profile_id) if db.schema_profile_id else None,
        schema_profile_name=db.schema_profile.name if getattr(db, "schema_profile", None) else None,
        created_at=db.created_at.isoformat() if db.created_at else None,
        updated_at=db.updated_at.isoformat() if db.updated_at else None,
        connections=_serialize_connections(db, connections=connections),
    )


def _to_detail_response(db, bundles=None, connections=None) -> LogicalDatabaseDetailResponse:
    """Конвертировать logical database в детальный ответ."""
    base = _to_response(db, connections=connections)
    return LogicalDatabaseDetailResponse(
        **base.model_dump(),
        bundles=[
            ScenarioBundleSummaryResponse(**bundle.to_dict())
            for bundle in (bundles or [])
        ],
    )


@router.get("/", response_model=LogicalDatabaseListResponse)
async def list_logical_databases(
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Получить список всех logical database с active-подключениями."""
    try:
        databases = await repo.get_all_with_connections()
        return LogicalDatabaseListResponse(
            databases=[_to_response(db) for db in databases]
        )
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка получения списка логических БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка логических БД: {e}")


@router.post("/", response_model=LogicalDatabaseResponse, status_code=201)
async def create_logical_database(
    data: LogicalDatabaseCreateRequest,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Создать новую logical database."""
    try:
        existing = await repo.get_by_name(data.name)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Логическая БД с именем '{data.name}' уже существует",
            )
        db = await repo.create(
            name=data.name,
            description=data.description,
            schema_profile_id=data.schema_profile_id,
        )
        return _to_response(db)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка создания логической БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания логической БД: {e}")


@router.get("/{logical_db_id}", response_model=LogicalDatabaseDetailResponse)
async def get_logical_database(
    logical_db_id: str,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Получить logical database по ID вместе с её bundle'ами."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        bundles = []
        if db.schema_profile_id:
            bundles = await get_bundle_repo().list_bundles(schema_profile_id=str(db.schema_profile_id))
        return _to_detail_response(db, bundles=bundles)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка получения логической БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения логической БД: {e}")


@router.put("/{logical_db_id}", response_model=LogicalDatabaseResponse)
async def update_logical_database(
    logical_db_id: str,
    data: LogicalDatabaseUpdateRequest,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Обновить logical database."""
    try:
        if data.name is not None:
            existing = await repo.get_by_name(data.name)
            if existing and str(existing.id) != logical_db_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Логическая БД с именем '{data.name}' уже существует",
                )
        db = await repo.update(
            logical_db_id=logical_db_id,
            name=data.name,
            description=data.description,
            schema_profile_id=data.schema_profile_id,
        )
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        if data.schema_profile_id is not None:
            profile = await get_profile_repo().get_profile_by_id(data.schema_profile_id) if data.schema_profile_id else None
            db = await repo.assign_profile(
                logical_db_id=logical_db_id,
                schema_profile_id=data.schema_profile_id,
                schema_profile_name=profile.name if profile else None,
                profile_source='inherited',
            )
        return _to_response(db)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка обновления логической БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления логической БД: {e}")


@router.put("/{logical_db_id}/profile", response_model=LogicalDatabaseDetailResponse)
async def assign_logical_database_profile(
    logical_db_id: str,
    data: LogicalDatabaseProfileAssignRequest,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Назначить schema_profile logical database и синхронизировать её подключения."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")

        profile_repo = get_profile_repo()
        bundle_repo = get_bundle_repo()
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

        fallback_reference_connection_id = next(
            (str(connection.id) for connection in db.connections if connection.is_active == 't'),
            None,
        )
        target_reference_connection_id = (
            data.reference_connection_id
            or (str(profile.reference_connection_id) if profile.reference_connection_id else None)
            or fallback_reference_connection_id
        )
        if target_reference_connection_id != (
            str(profile.reference_connection_id) if profile.reference_connection_id else None
        ):
            await profile_repo.update_profile(
                profile_id=str(profile.id),
                description=data.description if data.description is not None else profile.description,
                reference_connection_id=target_reference_connection_id,
            )

        updated = await repo.assign_profile(
            logical_db_id=logical_db_id,
            schema_profile_id=str(profile.id),
            schema_profile_name=profile.name,
            profile_source='inherited',
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")

        bundles = await bundle_repo.list_bundles(schema_profile_id=str(profile.id))
        return _to_detail_response(updated, bundles=bundles)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка назначения профиля logical database: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка назначения профиля logical database: {e}")


@router.post("/{logical_db_id}/bundles/generate", response_model=LogicalDatabaseBundlesGenerateResponse)
async def generate_logical_database_bundles(
    logical_db_id: str,
    data: ProfileBundleGenerateRequest,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Сгенерировать bundle'ы для logical database через её schema_profile."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        if not db.schema_profile_id:
            raise HTTPException(status_code=400, detail="Для logical database сначала назначьте schema_profile")

        active_connections = [connection for connection in db.connections if connection.is_active == 't']
        if not active_connections:
            raise HTTPException(status_code=400, detail="Для logical database нет активных подключений")

        reference_connection_id = (
            data.reference_connection_id
            or next((str(connection.id) for connection in active_connections), None)
        )
        if not reference_connection_id:
            raise HTTPException(status_code=400, detail="Не удалось определить reference_connection_id")

        reference_connection_ids = {str(connection.id) for connection in active_connections}
        if reference_connection_id not in reference_connection_ids:
            raise HTTPException(
                status_code=400,
                detail="reference_connection_id должен принадлежать выбранной logical database",
            )

        generator = ScenarioGenerator(
            connection_repo=get_connection_repo(),
            bundle_repository=get_bundle_repo(),
        )
        bundles = await generator.generate_bundles_for_profile(
            schema_profile_id=str(db.schema_profile_id),
            reference_connection_id=reference_connection_id,
            scenario_types=data.scenario_template_ids,
        )

        detail_db = await repo.get_by_id(logical_db_id)
        detail_bundles = await get_bundle_repo().list_bundles(schema_profile_id=str(db.schema_profile_id))
        return LogicalDatabaseBundlesGenerateResponse(
            logical_database=_to_detail_response(detail_db, bundles=detail_bundles),
            generated_count=len(bundles),
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка генерации bundle'ов logical database: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации bundle'ов logical database: {e}")


@router.get("/{logical_db_id}/validate")
async def validate_logical_database(
    logical_db_id: str,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
) -> Dict[str, Any]:
    """Проверить совместимость active-подключений logical database."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")

        active_connections = [connection for connection in db.connections if connection.is_active == 't']
        if not active_connections:
            raise HTTPException(status_code=400, detail="Для logical database нет активных подключений")

        validator = LogicalDatabaseValidator(get_connection_repo())
        return await validator.validate_connections(
            [str(connection.id) for connection in active_connections]
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка проверки logical database: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка проверки logical database: {e}")


@router.delete("/{logical_db_id}")
async def delete_logical_database(
    logical_db_id: str,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Удалить logical database (подключения сохраняются, но теряют привязку)."""
    try:
        deleted = await repo.delete(logical_db_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        return {"message": "Логическая БД удалена"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка удаления логической БД: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления логической БД: {e}")
