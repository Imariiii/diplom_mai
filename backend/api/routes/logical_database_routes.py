"""
API маршруты для управления логическими базами данных
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect

from backend import initialize
from backend.api.schemas.logical_database_schemas import (
    LogicalDatabaseBundlesGenerateResponse,
    LogicalDatabaseConnectionSummary,
    LogicalDatabaseCreateRequest,
    LogicalDatabaseDetailResponse,
    LogicalDatabaseListResponse,
    LogicalDatabaseProfileAssignRequest,
    LogicalDatabaseReferenceUpdateRequest,
    LogicalDatabaseResponse,
    LogicalDatabaseUpdateRequest,
    LogicalDatabaseValidationResponse,
)
from backend.api.schemas.profile_schemas import (
    ProfileBundleGenerateRequest,
    ScenarioBundleSummaryResponse,
)
from backend.database.repository.logical_database_repository import LogicalDatabaseRepository
from backend.database.logical_database_validator import LogicalDatabaseValidator
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.database.scenario_generator import DEFAULT_SCENARIO_TYPES, ScenarioGenerator

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
            detected_profile_name=connection.detected_profile_name,
            profile_confidence=connection.profile_confidence,
            profile_source=connection.profile_source,
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
        reference_connection_id=str(db.reference_connection_id) if getattr(db, "reference_connection_id", None) else None,
        reference_connection_name=(
            db.reference_connection.name if getattr(db, "reference_connection", None) else None
        ),
        profile_status=getattr(db, "profile_status", "draft"),
        compatibility_status=getattr(db, "compatibility_status", "unknown"),
        compatibility_report=getattr(db, "compatibility_report", None),
        validated_at=db.validated_at.isoformat() if getattr(db, "validated_at", None) else None,
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
        if profile.is_builtin != 't' and target_reference_connection_id != (
            str(profile.reference_connection_id) if profile.reference_connection_id else None
        ):
            await profile_repo.update_profile(
                profile_id=str(profile.id),
                description=data.description if data.description is not None else profile.description,
                reference_connection_id=target_reference_connection_id,
            )

        active_connections = [connection for connection in db.connections if connection.is_active == 't']
        if active_connections:
            active_ids = {str(connection.id) for connection in active_connections}
            if target_reference_connection_id not in active_ids:
                raise HTTPException(
                    status_code=400,
                    detail="reference_connection_id должен принадлежать выбранной logical database",
                )
            validator = LogicalDatabaseValidator(get_connection_repo())
            compatibility = await validator.validate_connections(
                [str(connection.id) for connection in active_connections],
                reference_connection_id=target_reference_connection_id,
                mode="strict",
            )
            if not compatibility.get("valid"):
                await repo.update_profile_state(
                    logical_db_id=logical_db_id,
                    profile_status="incompatible",
                    compatibility_status="invalid",
                    compatibility_report=compatibility,
                    reference_connection_id=target_reference_connection_id,
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Подключения logical database несовместимы: "
                        + "; ".join(compatibility.get("errors", []))
                    ),
                )
        else:
            compatibility = None

        updated = await repo.assign_profile(
            logical_db_id=logical_db_id,
            schema_profile_id=str(profile.id),
            schema_profile_name=profile.name,
            profile_source='inherited',
            reference_connection_id=target_reference_connection_id,
            profile_status="confirmed",
            compatibility_status=(
                "valid_with_warnings"
                if compatibility and compatibility.get("warnings")
                else "valid"
            ),
            compatibility_report=compatibility,
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
        if db.profile_status in {"draft", "needs_review", "incompatible"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Перед генерацией bundle'ов подтвердите профиль logical database "
                    f"(profile_status={db.profile_status})"
                ),
            )
        if db.compatibility_status == "invalid":
            raise HTTPException(
                status_code=400,
                detail="Перед генерацией bundle'ов исправьте несовместимость logical database",
            )

        active_connections = [connection for connection in db.connections if connection.is_active == 't']
        if not active_connections:
            raise HTTPException(status_code=400, detail="Для logical database нет активных подключений")
        pending_review_connections = [
            connection.name
            for connection in active_connections
            if connection.profile_source == "pending_review"
        ]
        if pending_review_connections:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Перед генерацией bundle'ов подтвердите schema_profile подключений: "
                    + ", ".join(pending_review_connections)
                ),
            )

        reference_connection_id = (
            data.reference_connection_id
            or (str(db.reference_connection_id) if db.reference_connection_id else None)
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

        validator = LogicalDatabaseValidator(get_connection_repo())
        compatibility = await validator.validate_connections(
            [str(connection.id) for connection in active_connections],
            reference_connection_id=reference_connection_id,
            mode="strict",
        )
        if not compatibility.get("valid"):
            await repo.update_profile_state(
                logical_db_id=logical_db_id,
                profile_status="incompatible",
                compatibility_status="invalid",
                compatibility_report=compatibility,
                reference_connection_id=reference_connection_id,
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Подключения logical database несовместимы: "
                    + "; ".join(compatibility.get("errors", []))
                ),
            )

        await repo.update_profile_state(
            logical_db_id=logical_db_id,
            profile_status="confirmed",
            compatibility_status="valid_with_warnings" if compatibility.get("warnings") else "valid",
            compatibility_report=compatibility,
            reference_connection_id=reference_connection_id,
        )

        generator = ScenarioGenerator(
            connection_repo=get_connection_repo(),
            bundle_repository=get_bundle_repo(),
        )
        bundles = await generator.generate_bundles_for_logical_database(
            logical_database_id=logical_db_id,
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


@router.get("/{logical_db_id}/validate", response_model=LogicalDatabaseValidationResponse)
async def validate_logical_database(
    logical_db_id: str,
    reference_connection_id: str | None = Query(default=None),
    mode: str = Query(default="lenient", pattern="^(lenient|strict)$"),
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
        effective_reference_connection_id = (
            reference_connection_id
            or (str(db.reference_connection_id) if getattr(db, "reference_connection_id", None) else None)
        )
        connection_ids = [str(connection.id) for connection in active_connections]
        compatibility = await validator.validate_connections(
            connection_ids,
            reference_connection_id=effective_reference_connection_id,
            mode=mode,
        )

        bundle_preflight: Dict[str, Any] = {}
        if len(active_connections) >= 2 and db.schema_profile_id:
            bundle_repo = get_bundle_repo()
            bundle_validator = ScenarioBundleValidator(get_connection_repo())
            resolver = ScenarioBundleResolver(get_connection_repo(), bundle_repo)
            for scenario_template_id in DEFAULT_SCENARIO_TYPES:
                preferred_name = f"{scenario_template_id}::{db.name}::common"
                bundle = await bundle_repo.get_bundle_for_profile_template(
                    schema_profile_id=str(db.schema_profile_id),
                    scenario_template_id=scenario_template_id,
                    preferred_name=preferred_name,
                )
                if not bundle:
                    bundle_preflight[scenario_template_id] = {
                        "valid": False,
                        "errors": [f"Common bundle '{preferred_name}' не найден"],
                        "warnings": [],
                    }
                    continue
                preflight = await bundle_validator.validate_bundle_for_connections(
                    bundle=resolver.bundle_to_execution_dict(bundle.to_dict()),
                    connection_ids=connection_ids,
                )
                bundle_preflight[scenario_template_id] = {
                    "valid": preflight.get("valid", False),
                    "errors": preflight.get("errors", []),
                    "warnings": preflight.get("warnings", []),
                }
            await bundle_validator.schema_analyzer.db_connection.close_all()

        compatibility["bundle_preflight"] = bundle_preflight
        preflight_failed = any(
            not item.get("valid", True)
            for item in bundle_preflight.values()
        )
        profile_status = "confirmed" if compatibility.get("valid") else "incompatible"
        if compatibility.get("valid") and preflight_failed:
            profile_status = "needs_review"

        await repo.update_profile_state(
            logical_db_id=logical_db_id,
            profile_status=profile_status,
            compatibility_status=(
                "invalid"
                if not compatibility.get("valid")
                else ("valid_with_warnings" if compatibility.get("warnings") else "valid")
            ),
            compatibility_report=compatibility,
            reference_connection_id=compatibility.get("reference_connection_id"),
        )
        return compatibility
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка проверки logical database: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка проверки logical database: {e}")


@router.put("/{logical_db_id}/reference-connection", response_model=LogicalDatabaseResponse)
async def update_logical_database_reference(
    logical_db_id: str,
    data: LogicalDatabaseReferenceUpdateRequest,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Назначить эталонное подключение logical database."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        active_ids = {
            str(connection.id)
            for connection in (db.connections or [])
            if connection.is_active == 't'
        }
        if data.reference_connection_id not in active_ids:
            raise HTTPException(
                status_code=400,
                detail="reference_connection_id должен принадлежать выбранной logical database",
            )
        updated = await repo.update_profile_state(
            logical_db_id=logical_db_id,
            reference_connection_id=data.reference_connection_id,
            compatibility_status="unknown",
        )
        return _to_response(updated)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка назначения reference connection: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка назначения reference connection: {e}")


@router.post("/{logical_db_id}/connections/{connection_id}/confirm-profile", response_model=LogicalDatabaseDetailResponse)
async def confirm_logical_database_connection_profile(
    logical_db_id: str,
    connection_id: str,
    repo: LogicalDatabaseRepository = Depends(get_logical_db_repo),
):
    """Подтвердить подключение через strict compatibility и синхронизировать профиль logical DB."""
    try:
        db = await repo.get_by_id(logical_db_id)
        if not db:
            raise HTTPException(status_code=404, detail="Логическая БД не найдена")
        if not db.schema_profile_id:
            raise HTTPException(status_code=400, detail="Для logical database сначала назначьте schema_profile")
        if connection_id not in {str(connection.id) for connection in (db.connections or [])}:
            raise HTTPException(status_code=400, detail="Подключение не принадлежит logical database")

        active_connections = [connection for connection in db.connections if connection.is_active == 't']
        reference_connection_id = (
            str(db.reference_connection_id)
            if getattr(db, "reference_connection_id", None)
            else connection_id
        )
        validator = LogicalDatabaseValidator(get_connection_repo())
        compatibility = await validator.validate_connections(
            [str(connection.id) for connection in active_connections],
            reference_connection_id=reference_connection_id,
            mode="strict",
        )
        if not compatibility.get("valid"):
            await repo.update_profile_state(
                logical_db_id=logical_db_id,
                profile_status="incompatible",
                compatibility_status="invalid",
                compatibility_report=compatibility,
                reference_connection_id=reference_connection_id,
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Подключения logical database несовместимы: "
                    + "; ".join(compatibility.get("errors", []))
                ),
            )

        updated = await repo.assign_profile(
            logical_db_id=logical_db_id,
            schema_profile_id=str(db.schema_profile_id),
            schema_profile_name=db.schema_profile.name if db.schema_profile else None,
            profile_source="inherited",
            reference_connection_id=reference_connection_id,
            profile_status="confirmed",
            compatibility_status="valid_with_warnings" if compatibility.get("warnings") else "valid",
            compatibility_report=compatibility,
        )
        bundles = await get_bundle_repo().list_bundles(schema_profile_id=str(db.schema_profile_id))
        return _to_detail_response(updated, bundles=bundles)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LOGICAL_DB] Ошибка подтверждения подключения logical database: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка подтверждения подключения logical database: {e}")


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
