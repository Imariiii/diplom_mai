"""
API роуты для управления состоянием БД
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/database", tags=["database"])


def get_db_state_manager():
    """Получить менеджер состояния БД"""
    from backend.main import get_db_state_manager
    return get_db_state_manager()


def get_db_connection():
    """Получить подключение к БД"""
    from backend.main import get_db_connection as main_get_db_connection
    return main_get_db_connection()


@router.get("/{dbms_type}/state")
async def get_database_state(dbms_type: str):
    """Получить текущее состояние БД (row counts, backup-таблицы)"""
    if dbms_type not in ['mysql', 'postgresql']:
        raise HTTPException(status_code=400, detail=f"Unsupported DB type: {dbms_type}")
    
    try:
        engine = get_db_connection().get_engine(dbms_type)
        state = await get_db_state_manager().get_database_state(engine, dbms_type)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dbms_type}/backup")
async def create_backup(dbms_type: str, request: dict | None = None):
    """Создать backup вручную"""
    from backend.api.schemas import BackupRequest, BackupResponse
    from sqlalchemy import inspect
    
    if dbms_type not in ['mysql', 'postgresql']:
        raise HTTPException(status_code=400, detail=f"Unsupported DB type: {dbms_type}")
    
    # Handle empty body or None
    backup_request = BackupRequest() if request is None else BackupRequest(**request)
    
    try:
        engine = get_db_connection().get_engine(dbms_type)
        state_manager = get_db_state_manager()
        
        # Если таблицы не указаны - backup всех таблиц
        if backup_request.tables:
            tables = set(request.tables)
        else:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
        
        # Для ручного backup используем стратегию напрямую
        backup_info = await state_manager._strategy.create_backup(engine, tables)
        
        if not backup_info:
            raise HTTPException(status_code=500, detail="Failed to create backup - strategy returned None")
        
        # Сохраняем в active_backups для возможности восстановления
        backup_key = f"{dbms_type}:{backup_info.backup_id}"
        state_manager._active_backups[backup_key] = backup_info
        
        return BackupResponse(
            backup_id=backup_info.backup_id,
            dbms_type=dbms_type,
            tables=list(backup_info.tables),
            row_counts=backup_info.row_counts,
            created_at=backup_info.created_at.isoformat()
        )
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[BACKUP ERROR] {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dbms_type}/restore")
async def restore_backup(dbms_type: str, request: dict | None = None):
    """Восстановить из существующего backup"""
    from backend.api.schemas import RestoreRequest, RestoreResponse
    
    if dbms_type not in ['mysql', 'postgresql']:
        raise HTTPException(status_code=400, detail=f"Unsupported DB type: {dbms_type}")
    
    restore_request = RestoreRequest() if request is None else RestoreRequest(**request)
    
    try:
        if restore_request.backup_id:
            engine = get_db_connection().get_engine(dbms_type)
            restore_result = await get_db_state_manager().manual_restore(
                engine, dbms_type, request.backup_id
            )
        else:
            raise HTTPException(status_code=400, detail="backup_id is required")
        
        return RestoreResponse(
            success=restore_result.success,
            duration_ms=restore_result.duration_ms,
            verified=restore_result.verified,
            errors=restore_result.errors
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dbms_type}/cleanup")
async def cleanup_backups(dbms_type: str):
    """Удалить backup-таблицы"""
    from backend.api.schemas import CleanupResponse
    
    if dbms_type not in ['mysql', 'postgresql']:
        raise HTTPException(status_code=400, detail=f"Unsupported DB type: {dbms_type}")
    
    try:
        engine = get_db_connection().get_engine(dbms_type)
        deleted = await get_db_state_manager().cleanup_all_backups(engine, dbms_type)
        return CleanupResponse(deleted_tables=deleted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dbms_type}/estimate")
async def estimate_backup(dbms_type: str, tables: str):
    """Оценить размер backup для указанных таблиц"""
    from backend.api.schemas import EstimateResponse
    
    if dbms_type not in ['mysql', 'postgresql']:
        raise HTTPException(status_code=400, detail=f"Unsupported DB type: {dbms_type}")
    
    try:
        engine = get_db_connection().get_engine(dbms_type)
        table_list = tables.split(',')
        
        size_estimate = await get_db_state_manager()._strategy.estimate_size(
            engine, set(table_list)
        )
        
        return EstimateResponse(
            tables=size_estimate.tables,
            total_rows=size_estimate.total_rows,
            total_size_bytes=size_estimate.total_size_bytes,
            estimated_time_sec=size_estimate.estimated_backup_time_sec,
            warnings=size_estimate.warnings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))