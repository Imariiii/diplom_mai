"""
API роуты для управления состоянием БД
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect

from backend import initialize
from backend.api.schemas import BackupRequest, BackupResponse, CleanupResponse, EstimateResponse, RestoreRequest, RestoreResponse
from backend.database.connection import DatabaseConnection
from backend.database.repository.connection_repository import ConnectionRepository

router = APIRouter(prefix="/api/database", tags=["database"])


def get_db_state_manager():
    """Получить менеджер состояния БД"""
    from backend.main import get_db_state_manager as main_get_db_state_manager
    return main_get_db_state_manager()


def get_db_connection() -> DatabaseConnection:
    """Получить менеджер подключений к БД"""
    from backend.main import get_db_connection as main_get_db_connection
    return main_get_db_connection()


def get_connection_repo() -> ConnectionRepository:
    """Получить репозиторий подключений"""
    if not hasattr(initialize, "connection_repository") or initialize.connection_repository is None:
        raise HTTPException(status_code=500, detail="ConnectionRepository не инициализирован")
    return initialize.connection_repository


async def _resolve_connection_by_type(
    dbms_type: str,
    repo: ConnectionRepository,
) -> Dict[str, str]:
    """Разрешить legacy dbms_type в явное активное подключение"""
    if dbms_type not in {"mysql", "postgresql"}:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип БД: {dbms_type}")

    connections = await repo.get_active_connections()
    matches = [conn for conn in connections if conn.dbms_type == dbms_type]

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Активное подключение типа '{dbms_type}' не найдено. "
                "Создайте его через UI/API или используйте route с connection_id."
            ),
        )

    if len(matches) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Найдено несколько активных подключений типа '{dbms_type}'. "
                "Используйте route с явным connection_id."
            ),
        )

    match = matches[0]
    return {
        "connection_id": str(match.id),
        "dbms_type": match.dbms_type,
        "name": match.name,
    }


async def _resolve_connection_by_id(
    connection_id: str,
    repo: ConnectionRepository,
) -> Dict[str, Any]:
    """Получить явное подключение по ID"""
    resolved_connection_id = connection_id
    if connection_id in {"mysql", "postgresql"}:
        resolved = await _resolve_connection_by_type(connection_id, repo)
        resolved_connection_id = resolved["connection_id"]

    decrypted = await repo.get_decrypted_connection(resolved_connection_id)
    if not decrypted:
        raise HTTPException(status_code=404, detail="Подключение не найдено")
    return decrypted


async def _get_connection_context(
    connection_id: str,
    repo: ConnectionRepository,
) -> Dict[str, Any]:
    """Собрать контекст подключения для database-state операций"""
    db_connection = get_db_connection()
    db_connection.set_connection_repository(repo)
    resolved_connection_id = connection_id
    if connection_id in {"mysql", "postgresql"}:
        resolved = await _resolve_connection_by_type(connection_id, repo)
        resolved_connection_id = resolved["connection_id"]

    connection_config = await _resolve_connection_by_id(resolved_connection_id, repo)
    await db_connection.ensure_connection_config(resolved_connection_id)

    return {
        "connection_id": resolved_connection_id,
        "connection_name": connection_config["name"],
        "dbms_type": connection_config["dbms_type"],
        "engine": await db_connection.get_engine_async(resolved_connection_id),
    }


async def _build_database_state(connection_id: str, repo: ConnectionRepository) -> Dict[str, Any]:
    """Получить состояние БД с метаданными подключения"""
    context = await _get_connection_context(connection_id, repo)
    state = await get_db_state_manager().get_database_state(context["engine"], context["dbms_type"])
    state["connection_id"] = context["connection_id"]
    state["connection_name"] = context["connection_name"]
    return state


async def _create_backup_for_connection(
    connection_id: str,
    backup_request: BackupRequest,
    repo: ConnectionRepository,
) -> BackupResponse:
    """Создать backup для конкретного подключения"""
    context = await _get_connection_context(connection_id, repo)
    state_manager = get_db_state_manager()

    if backup_request.tables:
        tables = set(backup_request.tables)
    else:
        async with context["engine"].connect() as conn:
            tables = set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))

    backup_info = await state_manager._strategy.create_backup(context["engine"], tables)
    if not backup_info:
        raise HTTPException(status_code=500, detail="Не удалось создать backup")

    backup_key = f"{context['dbms_type']}:{backup_info.backup_id}"
    state_manager._active_backups[backup_key] = backup_info

    return BackupResponse(
        backup_id=backup_info.backup_id,
        dbms_type=context["dbms_type"],
        tables=list(backup_info.tables),
        row_counts=backup_info.row_counts,
        created_at=backup_info.created_at.isoformat(),
    )


async def _restore_backup_for_connection(
    connection_id: str,
    restore_request: RestoreRequest,
    repo: ConnectionRepository,
) -> RestoreResponse:
    """Восстановить backup для конкретного подключения"""
    context = await _get_connection_context(connection_id, repo)
    restore_result = await get_db_state_manager().manual_restore(
        context["engine"], context["dbms_type"], restore_request.backup_id
    )

    return RestoreResponse(
        success=restore_result.success,
        duration_ms=restore_result.duration_ms,
        verified=restore_result.verified,
        errors=restore_result.errors,
    )


async def _cleanup_backups_for_connection(
    connection_id: str,
    repo: ConnectionRepository,
) -> CleanupResponse:
    """Очистить backup-таблицы для конкретного подключения"""
    context = await _get_connection_context(connection_id, repo)
    deleted = await get_db_state_manager().cleanup_all_backups(context["engine"], context["dbms_type"])
    return CleanupResponse(deleted_tables=deleted)


async def _estimate_backup_for_connection(
    connection_id: str,
    tables: str,
    repo: ConnectionRepository,
) -> EstimateResponse:
    """Оценить размер backup для конкретного подключения"""
    context = await _get_connection_context(connection_id, repo)
    table_list = [table for table in tables.split(",") if table]

    size_estimate = await get_db_state_manager()._strategy.estimate_size(
        context["engine"],
        set(table_list),
    )

    return EstimateResponse(
        tables=size_estimate.tables,
        total_rows=size_estimate.total_rows,
        total_size_bytes=size_estimate.total_size_bytes,
        estimated_time_sec=size_estimate.estimated_backup_time_sec,
        warnings=size_estimate.warnings,
    )


@router.get("/connections/{connection_id}/state")
async def get_database_state_by_connection(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Получить текущее состояние БД по ID подключения"""
    try:
        return await _build_database_state(connection_id, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/backup")
async def create_backup_by_connection(
    connection_id: str,
    request: Optional[Dict[str, Any]] = None,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Создать backup вручную по ID подключения"""
    backup_request = BackupRequest() if request is None else BackupRequest(**request)

    try:
        return await _create_backup_for_connection(connection_id, backup_request, repo)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[BACKUP ERROR] {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/restore")
async def restore_backup_by_connection(
    connection_id: str,
    request: Optional[Dict[str, Any]] = None,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Восстановить backup по ID подключения"""
    restore_request = RestoreRequest() if request is None else RestoreRequest(**request)

    try:
        return await _restore_backup_for_connection(connection_id, restore_request, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/cleanup")
async def cleanup_backups_by_connection(
    connection_id: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Удалить backup-таблицы по ID подключения"""
    try:
        return await _cleanup_backups_for_connection(connection_id, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}/estimate")
async def estimate_backup_by_connection(
    connection_id: str,
    tables: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Оценить размер backup по ID подключения"""
    try:
        return await _estimate_backup_for_connection(connection_id, tables, repo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dbms_type}/state")
async def get_database_state(
    dbms_type: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Legacy route: получить состояние БД по типу СУБД"""
    resolved = await _resolve_connection_by_type(dbms_type, repo)
    return await _build_database_state(resolved["connection_id"], repo)


@router.post("/{dbms_type}/backup")
async def create_backup(
    dbms_type: str,
    request: Optional[Dict[str, Any]] = None,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Legacy route: создать backup по типу СУБД"""
    backup_request = BackupRequest() if request is None else BackupRequest(**request)
    resolved = await _resolve_connection_by_type(dbms_type, repo)
    return await _create_backup_for_connection(resolved["connection_id"], backup_request, repo)


@router.post("/{dbms_type}/restore")
async def restore_backup(
    dbms_type: str,
    request: Optional[Dict[str, Any]] = None,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Legacy route: восстановить backup по типу СУБД"""
    restore_request = RestoreRequest() if request is None else RestoreRequest(**request)
    resolved = await _resolve_connection_by_type(dbms_type, repo)
    return await _restore_backup_for_connection(resolved["connection_id"], restore_request, repo)


@router.post("/{dbms_type}/cleanup")
async def cleanup_backups(
    dbms_type: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Legacy route: удалить backup-таблицы по типу СУБД"""
    resolved = await _resolve_connection_by_type(dbms_type, repo)
    return await _cleanup_backups_for_connection(resolved["connection_id"], repo)


@router.get("/{dbms_type}/estimate")
async def estimate_backup(
    dbms_type: str,
    tables: str,
    repo: ConnectionRepository = Depends(get_connection_repo),
):
    """Legacy route: оценить backup по типу СУБД"""
    resolved = await _resolve_connection_by_type(dbms_type, repo)
    return await _estimate_backup_for_connection(resolved["connection_id"], tables, repo)
