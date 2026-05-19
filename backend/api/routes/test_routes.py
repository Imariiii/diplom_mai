"""
API роуты для выполнения тестов
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
import uuid
import asyncio

from backend.api.schemas import AsyncTestRequest
from backend.core.summary_utils import sanitize_test_summary
from backend.database.bundle_workload import get_bundle_workload_mode, get_primary_rate_unit
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.load_tester.tester import LoadTester, TestCancelledError
from backend.load_tester.warmup import build_warmup_metadata, merge_warmup_run_stats
from backend.websocket_manager import manager, TestStreamingCallback, TestStatusUpdate

router = APIRouter(prefix="/test", tags=["test"])


BLOCKING_LOGICAL_PROFILE_STATUSES = {"draft", "needs_review", "incompatible"}
TERMINAL_TEST_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_TEST_TTL = timedelta(hours=6)
RUNTIME_ONLY_KEYS = {"_task", "_tester"}


def _extract_raw_samples(stats: Dict) -> List[Dict]:
    """Извлечь raw sample-метрики из статистики теста"""
    raw_samples = stats.get("raw_samples", []) or []
    if "raw_samples" in stats:
        del stats["raw_samples"]
    return raw_samples


def get_active_tests():
    """Получить хранилище активных тестов из main.py"""
    from backend.main import active_tests
    return active_tests


def _now_utc() -> datetime:
    """Получить текущий UTC timestamp для active_tests."""
    return datetime.now(timezone.utc)


def _parse_active_test_timestamp(value) -> Optional[datetime]:
    """Безопасно разобрать timestamp из active_tests."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def prune_active_tests(active_tests: Dict[str, Dict] = None, now: datetime = None) -> int:
    """Удалить завершённые in-memory тесты старше TTL."""
    active_tests = active_tests if active_tests is not None else get_active_tests()
    now = now or _now_utc()
    pruned = 0

    for test_id, test_info in list(active_tests.items()):
        if test_info.get("status") not in TERMINAL_TEST_STATUSES:
            continue

        finished_at = _parse_active_test_timestamp(
            test_info.get("finished_at") or test_info.get("created_at")
        )
        if finished_at and now - finished_at > ACTIVE_TEST_TTL:
            del active_tests[test_id]
            pruned += 1

    return pruned


def _build_bundle_config_snapshot(bundle: Dict) -> Dict:
    """Собрать bundle snapshot для истории и comparison."""
    workload_mode = bundle.get("workload_mode") or "query"
    return {
        "id": bundle.get("id"),
        "name": bundle.get("name"),
        "description": bundle.get("description"),
        "scenario_template_id": bundle.get("scenario_template_id"),
        "scenario_template_name": bundle.get("scenario_template_name"),
        "schema_profile_id": bundle.get("schema_profile_id"),
        "schema_profile_name": bundle.get("schema_profile_name"),
        "generation_source": bundle.get("generation_source"),
        "is_builtin": bundle.get("is_builtin"),
        "workload_mode": workload_mode,
        "primary_rate_unit": bundle.get("primary_rate_unit")
        or ("tps" if workload_mode == "transaction" else "qps"),
        "queries": bundle.get("queries", []),
        "transactions": bundle.get("transactions", []),
        "indexes": bundle.get("indexes", []),
    }


def _public_test_info(test_info: Dict) -> Dict:
    """Вернуть сериализуемую информацию о тесте без runtime-полей."""
    return {k: v for k, v in test_info.items() if k not in RUNTIME_ONLY_KEYS}


async def _validate_logical_database_run_request(request: AsyncTestRequest, scenario: str) -> None:
    """Серверная проверка logical DB state до постановки теста в фон."""
    if scenario == "custom" or not request.connection_ids:
        return

    from backend.initialize import connection_repository, logical_database_repository
    from backend.database.logical_database_validator import LogicalDatabaseValidator

    if not connection_repository:
        return

    connections = await connection_repository.bulk_get_connections(request.connection_ids)
    if len(connections) != len(request.connection_ids):
        raise HTTPException(status_code=400, detail="Не удалось загрузить все выбранные подключения")

    logical_database_ids = {
        str(connection.logical_database_id)
        for connection in connections
        if connection.logical_database_id
    }
    if not logical_database_ids:
        return
    if len(logical_database_ids) != 1 or any(not connection.logical_database_id for connection in connections):
        raise HTTPException(
            status_code=400,
            detail=(
                "Нельзя запускать scenario test сразу для нескольких logical database "
                "или смешивать их с подключениями без logical database"
            ),
        )

    logical_database_id = next(iter(logical_database_ids))
    if request.logical_database_id and request.logical_database_id != logical_database_id:
        raise HTTPException(
            status_code=400,
            detail="logical_database_id запроса не соответствует выбранным подключениям",
        )

    logical_database = connections[0].logical_database
    if logical_database_repository:
        logical_database = await logical_database_repository.get_by_id(logical_database_id)
    if not logical_database:
        raise HTTPException(status_code=400, detail="Логическая БД не найдена")

    profile_status = getattr(logical_database, "profile_status", "confirmed")
    compatibility_status = getattr(logical_database, "compatibility_status", "unknown")
    if profile_status in BLOCKING_LOGICAL_PROFILE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Logical database '{logical_database.name}' требует проверки профиля "
                f"(profile_status={profile_status})"
            ),
        )
    if compatibility_status == "invalid":
        raise HTTPException(
            status_code=400,
            detail=f"Logical database '{logical_database.name}' помечена как несовместимая",
        )

    pending_review_connections = [
        connection.name
        for connection in connections
        if getattr(connection, "profile_source", None) == "pending_review"
    ]
    if pending_review_connections:
        raise HTTPException(
            status_code=400,
            detail=(
                "Для части подключений schema_profile ещё требует подтверждения: "
                + ", ".join(pending_review_connections)
            ),
        )

    validator = LogicalDatabaseValidator(connection_repository)
    reference_connection_id = (
        str(logical_database.reference_connection_id)
        if getattr(logical_database, "reference_connection_id", None)
        else None
    )
    compatibility = await validator.validate_connections(
        request.connection_ids,
        reference_connection_id=reference_connection_id,
        mode="strict",
    )
    if logical_database_repository:
        await logical_database_repository.update_profile_state(
            logical_db_id=logical_database_id,
            profile_status="confirmed" if compatibility.get("valid") else "incompatible",
            compatibility_status=(
                "invalid"
                if not compatibility.get("valid")
                else ("valid_with_warnings" if compatibility.get("warnings") else "valid")
            ),
            compatibility_report=compatibility,
            reference_connection_id=compatibility.get("reference_connection_id"),
        )
    if not compatibility.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Подключения logical database несовместимы: "
                + "; ".join(compatibility.get("errors", []))
            ),
        )


@router.post("/async")
async def run_async_test(request: AsyncTestRequest):
    """
    Асинхронный запуск теста с WebSocket обновлениями.
    Возвращает test_id для подписки на обновления.
    """
    scenario = request.scenario or "mixed_light"
    if scenario == "custom":
        if not request.custom_sql:
            raise HTTPException(
                status_code=422,
                detail="Режим 'custom' требует параметр custom_sql с SQL-запросом",
            )
        from backend.load_tester.sql_validator import validate_custom_sql

        is_valid, validation_errors = validate_custom_sql(request.custom_sql)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail="Невалидный SQL-запрос: " + "; ".join(validation_errors),
            )

    await _validate_logical_database_run_request(request, scenario)

    from backend.initialize import HISTORY_ENABLED, test_repository
    
    test_id = str(uuid.uuid4())
    test_name = request.test_name or f"Тест {test_id}"
    
    active_tests = get_active_tests()
    prune_active_tests(active_tests)
    created_at = _now_utc()
    
    # Сохраняем информацию о тесте
    active_tests[test_id] = {
        "id": test_id,
        "name": test_name,
        "status": "pending",
        "config": request.model_dump(),
        "created_at": created_at,
        "finished_at": None,
    }
    
    # Создаём запись в БД истории (если включена)
    if HISTORY_ENABLED and test_repository:
        try:
            from datetime import datetime, timezone
            await test_repository.create_test_run(
                name=test_name,
                config=request.model_dump(),
                status='pending',
                test_run_id=test_id,
                logical_database_id=request.logical_database_id,
            )
        except Exception as e:
            print(f"[HISTORY_DB] ❌ Ошибка создания записи в БД истории: {e}")
    
    # Запускаем тест в фоне как asyncio Task для поддержки отмены
    task = asyncio.create_task(run_test_with_streaming(test_id, request))
    active_tests[test_id]["_task"] = task
    
    return {
        "test_id": test_id,
        "name": test_name,
        "status": "pending",
        "websocket_url": f"/ws/test/{test_id}",
        "message": "Тест запущен. Подключитесь к WebSocket для получения обновлений."
    }


async def run_test_with_streaming(test_id: str, request: AsyncTestRequest):
    """Фоновая задача для выполнения теста с WebSocket стримингом"""
    import time
    
    from backend.initialize import (
        HISTORY_ENABLED, 
        test_repository, 
        connection_repository,
        scenario_bundle_repository,
    )
    
    active_tests = get_active_tests()
    
    start_ts = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    
    streaming_callback = TestStreamingCallback(
        test_id,
        manager,
        repository=test_repository if HISTORY_ENABLED and test_repository else None,
    )
    streaming_callback.set_wall_start(start_ts)
    
    from backend.core.config import settings
    
    test_tester = LoadTester(connection_repo=connection_repository)
    test_tester.set_streaming_callback(streaming_callback)
    test_tester.set_backup_callback(streaming_callback.on_backup_status)
    test_tester.auto_restore = settings.restore.auto_restore
    if test_id in active_tests:
        active_tests[test_id]["_tester"] = test_tester
        active_tests[test_id]["_streaming_callback"] = streaming_callback
        if active_tests[test_id].get("status") == "cancelling":
            test_tester.request_cancel()
    
    # Разрешаем connection_ids в качестве уникальных ключей подключения
    connection_ids = request.connection_ids
    db_keys = request.db_types
    connection_names = {}  # mapping: connection_key -> connection_name
    connection_db_types = {}  # mapping: connection_key -> dbms_type
    
    if connection_ids and connection_repository:
        try:
            connections_info = {}
            resolved_db_keys = []
            for conn_id in connection_ids:
                decrypted = await connection_repository.get_decrypted_connection(conn_id)
                if decrypted:
                    connection_key = str(decrypted['id'])
                    db_type = decrypted['dbms_type']
                    conn_name = decrypted.get('name', connection_key)
                    connections_info[connection_key] = decrypted
                    connection_names[connection_key] = conn_name
                    connection_db_types[connection_key] = db_type
                    if connection_key not in resolved_db_keys:
                        resolved_db_keys.append(connection_key)
                    print(f"[TEST] Подключение {conn_id} -> {connection_key} ({db_type}, {conn_name})")
            
            # Регистрируем подключения в DatabaseConnection тестера
            test_tester.db_connection._connection_configs = connections_info
            test_tester.db_connection._connections_loaded = True
            db_keys = resolved_db_keys
            active_tests[test_id]["connection_names"] = connection_names
            active_tests[test_id]["connection_db_types"] = connection_db_types
        except Exception as e:
            print(f"[TEST] Ошибка загрузки подключений: {e}")
            import traceback
            traceback.print_exc()
            active_tests[test_id]["status"] = "failed"
            active_tests[test_id]["error"] = f"Ошибка загрузки подключений: {e}"
            active_tests[test_id]["finished_at"] = _now_utc()
            await streaming_callback.on_test_error(f"Ошибка загрузки подключений: {e}")
            return
    elif not db_keys:
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = "Не указаны connection_ids или db_types"
        active_tests[test_id]["finished_at"] = _now_utc()
        await streaming_callback.on_test_error("Не указаны connection_ids или db_types")
        return
    
    if not db_keys:
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = "Не удалось определить тип БД"
        active_tests[test_id]["finished_at"] = _now_utc()
        await streaming_callback.on_test_error("Не удалось определить тип БД")
        return

    # Дополнить config для истории и UI: типы СУБД и снимок имён подключений (в т.ч. для custom SQL)
    if connection_names or connection_db_types:
        enriched_config = dict(active_tests[test_id]["config"])
        if connection_db_types:
            unique_db_types = sorted({str(v) for v in connection_db_types.values() if v})
            if unique_db_types:
                enriched_config["db_types"] = unique_db_types
        if connection_names:
            enriched_config["connection_names_snapshot"] = {
                str(k): str(v) for k, v in connection_names.items()
            }
        active_tests[test_id]["config"] = enriched_config
        if HISTORY_ENABLED and test_repository:
            try:
                await test_repository.update_test_run_config(test_id, enriched_config)
            except Exception as exc:
                print(f"[HISTORY_DB] ⚠ Не удалось сохранить обогащённый config теста {test_id}: {exc}")

    print(f"[TEST] Запуск теста с db_keys={db_keys}, connection_names={connection_names}")
    print(
        f"[TEST] Параметры: итераций={request.iterations}, VU={request.virtual_users}, "
        f"warmup={request.warmup_time}s, индексы={request.use_indexes}"
    )
    
    try:
        if active_tests.get(test_id, {}).get("status") != "cancelling":
            active_tests[test_id]["status"] = "running"
            await streaming_callback.on_test_start()
        else:
            await streaming_callback.on_status_change(
                "cancelling",
                "Остановка теста: завершаем текущие операции…",
            )

        for db_key in db_keys:
            streaming_callback.ensure_dbms_runtime_stats(db_key)

        enriched_run = dict(active_tests[test_id].get("config") or {})
        enriched_run["cache_metric_mode"] = "delta"
        enriched_run["cache_metric_model"] = "hybrid"
        enriched_run["measurement_boundary_version"] = 2
        enriched_run.update(build_warmup_metadata(request.warmup_time))
        active_tests[test_id]["config"] = enriched_run
        if HISTORY_ENABLED and test_repository:
            try:
                await test_repository.update_test_run_config(test_id, enriched_run)
            except Exception as exc:
                print(f"[HISTORY_DB] ⚠ Не удалось сохранить cache_metric_mode: {exc}")

        scenario = request.scenario or "mixed_light"

        if scenario == "custom" and request.custom_sql:
            print(f"[TEST] Запуск пользовательского SQL-запроса")
            results = await test_tester.run_custom_sql_test(
                custom_sql=request.custom_sql,
                db_types=db_keys,
                iterations=request.iterations,
                virtual_users=request.virtual_users,
                warmup_time=request.warmup_time,
            )
        elif request.bundle_id or scenario != "custom":
            if not connection_ids or not connection_repository or not scenario_bundle_repository:
                raise ValueError("Scenario bundle требует connection_ids и доступного bundle repository")

            print(f"[TEST] Разрешение сценария: bundle_id={request.bundle_id!r}, scenario={scenario!r}")
            bundle_resolver = ScenarioBundleResolver(
                connection_repository=connection_repository,
                bundle_repository=scenario_bundle_repository,
            )
            resolved = await bundle_resolver.resolve_for_connections(
                connection_ids=connection_ids,
                scenario_template_id=scenario if scenario != "custom" else None,
                bundle_id=request.bundle_id,
            )
            resolved_bundle = resolved["bundle"]
            workload_mode = get_bundle_workload_mode(resolved_bundle)
            units_count = (
                len(resolved_bundle.get("transactions", []))
                if workload_mode == "transaction"
                else len(resolved_bundle.get("queries", []))
            )
            units_label = "транзакций" if workload_mode == "transaction" else "запросов"
            print(
                f"[TEST] Разрешён bundle: {resolved_bundle['name']!r} "
                f"(профиль: {resolved['schema_profile_name']!r}), "
                f"режим: {workload_mode}, {units_label}: {units_count}"
            )
            resolved_config = dict(active_tests[test_id]["config"])
            resolved_config.update({
                "scenario": resolved["scenario_template_id"],
                "scenario_template_id": resolved["scenario_template_id"],
                "resolved_bundle_id": resolved_bundle["id"],
                "resolved_bundle_name": resolved_bundle["name"],
                "resolved_bundle_description": resolved_bundle.get("description"),
                "resolved_profile_id": resolved["schema_profile_id"],
                "resolved_profile_name": resolved["schema_profile_name"],
                "workload_mode": workload_mode,
                "primary_rate_unit": get_primary_rate_unit(workload_mode),
                "comparison_unit": "transaction" if workload_mode == "transaction" else "query",
                "resolved_bundle_snapshot": _build_bundle_config_snapshot(resolved_bundle),
            })
            active_tests[test_id]["config"] = resolved_config
            active_tests[test_id]["resolved_profile"] = resolved["schema_profile_name"]
            active_tests[test_id]["resolved_bundle_id"] = resolved_bundle["id"]
            if HISTORY_ENABLED and test_repository:
                try:
                    await test_repository.update_test_run_config(test_id, resolved_config)
                except Exception as exc:
                    print(f"[HISTORY_DB] ⚠ Не удалось обновить config теста {test_id}: {exc}")

            bundle_validator = ScenarioBundleValidator(connection_repository)
            preflight = await bundle_validator.validate_bundle_for_connections(
                bundle=resolved_bundle,
                connection_ids=connection_ids,
            )
            if not preflight.get("valid"):
                raise ValueError(
                    "Сценарий не может быть запущен для выбранных БД. "
                    "Проверка совместимости SQL bundle обнаружила ошибки: "
                    + "; ".join(preflight.get("errors", []))
                    + ". Для PostgreSQL/Pagila убедитесь, что на PK настроены sequence "
                    "(см. ../pagila_new/rebuild.sh). Перегенерируйте common bundle: "
                    "POST /api/logical-databases/{id}/bundles/generate. "
                    "Проверка: GET /api/logical-databases/{id}/validate."
                )
            if preflight.get("warnings"):
                print(f"[TEST] Предупреждения preflight: {preflight['warnings']}")

            results = await test_tester.run_resolved_scenario_test_suite(
                scenario=resolved_bundle,
                db_types=db_keys,
                iterations=request.iterations,
                virtual_users=request.virtual_users,
                warmup_time=request.warmup_time,
                use_indexes=request.use_indexes,
            )
        else:
            error_msg = "Режим 'custom' требует параметр custom_sql с SQL-запросом"
            print(f"[TEST] {error_msg}")
            active_tests[test_id]["status"] = "failed"
            active_tests[test_id]["error"] = error_msg
            active_tests[test_id]["finished_at"] = _now_utc()
            await streaming_callback.on_test_error(error_msg)
            return

        warmup_stats = test_tester.get_warmup_stats_per_db()
        enriched_after_run = merge_warmup_run_stats(
            dict(active_tests[test_id].get("config") or {}),
            warmup_stats,
        )
        active_tests[test_id]["config"] = enriched_after_run
        if HISTORY_ENABLED and test_repository:
            try:
                await test_repository.update_test_run_config(test_id, enriched_after_run)
            except Exception as exc:
                print(f"[HISTORY_DB] ⚠ Не удалось сохранить warmup metadata: {exc}")

        await streaming_callback.on_status_change(
            "running",
            "Финализация результатов: сбор метрик и сохранение…",
        )

        system_metrics = {}
        dbms_metrics = {}
        workload_context = test_tester.get_workload_context()
        for db_key in db_keys:
            try:
                system_metrics[db_key] = await test_tester.get_system_metrics(db_key)
                end_counters = test_tester.get_measurement_end_counters(db_key)
                if not end_counters:
                    end_counters = await test_tester.get_dbms_metric_counters(db_key)
                latest_dbms_metrics = await test_tester.get_dbms_metrics(db_key)
                dbms_metrics[db_key] = test_tester.build_final_dbms_metrics(
                    db_key=db_key,
                    latest_metrics=latest_dbms_metrics,
                    start_counters=test_tester.get_measurement_start_counters(db_key),
                    end_counters=end_counters,
                    runtime_stats=streaming_callback.get_dbms_runtime_stats(db_key),
                    workload_context=workload_context,
                )
            except Exception as e:
                print(f"Ошибка сбора метрик для {db_key}: {e}")

        total_transactions = 0
        for result in results:
            if 'comparison' in result:
                for db_type, stats in result.get('comparison', {}).items():
                    total_transactions += stats.get('successful', 0) + stats.get('failed', 0)
            elif 'stats' in result:
                total_transactions += result['stats'].get('successful', 0) + result['stats'].get('failed', 0)

        if HISTORY_ENABLED and test_repository:
            try:
                for result in results:
                    if 'comparison' in result:
                        for db_key, stats in result.get('comparison', {}).items():
                            raw_samples = _extract_raw_samples(stats)
                            stats['connection_key'] = db_key
                            stats['db_name'] = connection_names.get(db_key, db_key)
                            await test_repository.add_test_result(
                                test_run_id=test_id,
                                db_type=stats.get('db_type', connection_db_types.get(db_key, db_key)),
                                metrics=stats,
                                query_id=result.get('query_id'),
                                system_metrics=system_metrics.get(db_key),
                                dbms_metrics=dbms_metrics.get(db_key)
                            )
                            await test_repository.add_metric_sample_batch(
                                test_run_id=test_id,
                                samples=raw_samples
                            )
                    elif 'stats' in result and 'db_key' in result:
                        db_key = result['db_key']
                        stats = result['stats']
                        raw_samples = _extract_raw_samples(stats)
                        stats['connection_key'] = db_key
                        stats['db_name'] = connection_names.get(db_key, db_key)
                        scenario_name = result.get('scenario', 'unknown')
                        await test_repository.add_test_result(
                            test_run_id=test_id,
                            db_type=stats.get('db_type', connection_db_types.get(db_key, db_key)),
                            metrics=stats,
                            query_id=f"scenario:{scenario_name}",
                            system_metrics=system_metrics.get(db_key),
                            dbms_metrics=dbms_metrics.get(db_key)
                        )
                        await test_repository.add_metric_sample_batch(
                            test_run_id=test_id,
                            samples=raw_samples
                        )
            except Exception as e:
                print(f"[HISTORY_DB] ❌ Ошибка сохранения в БД истории: {e}")

        await streaming_callback.drain_realtime_metrics()

        end_time = time.perf_counter()
        actual_duration = end_time - start_time
        finish_ts = start_ts + timedelta(seconds=actual_duration)

        run_config = active_tests[test_id].get("config") or {}
        workload_mode = run_config.get("workload_mode") or "query"
        primary_rate_unit = run_config.get("primary_rate_unit") or get_primary_rate_unit(workload_mode)
        summary = sanitize_test_summary({
            'workload_mode': workload_mode,
            'primary_rate_unit': primary_rate_unit,
            'comparison_unit': run_config.get("comparison_unit")
            or ("transaction" if workload_mode == "transaction" else "query"),
            'total_units': total_transactions,
            'total_transactions': total_transactions,
            'total_duration': actual_duration,
        })
        units_label = "транзакций" if workload_mode == "transaction" else "операций"
        print(
            f"[TEST] Тест {test_id} завершён за {actual_duration:.1f}с. "
            f"Единиц нагрузки ({units_label}): {total_transactions}"
        )

        if HISTORY_ENABLED and test_repository:
            try:
                await test_repository.update_test_run_status(
                    test_id,
                    'completed',
                    summary,
                    started_at=start_ts,
                    finished_at=finish_ts
                )
            except Exception as e:
                print(f"[HISTORY_DB] ❌ Ошибка обновления статуса теста: {e}")
        
        # Добавляем connection_names в результаты для frontend
        for result in results:
            if 'comparison' in result:
                new_comparison = {}
                for db_key, stats in result.get('comparison', {}).items():
                    stats['connection_key'] = db_key
                    stats['db_name'] = connection_names.get(db_key, db_key)
                    new_comparison[db_key] = stats
                result['comparison'] = new_comparison
            elif 'db_key' in result:
                result['db_name'] = connection_names.get(result['db_key'], result['db_key'])

        active_tests[test_id]["status"] = "completed"
        active_tests[test_id]["results"] = results
        active_tests[test_id]["summary"] = summary
        active_tests[test_id]["system_metrics"] = system_metrics
        active_tests[test_id]["dbms_metrics"] = dbms_metrics
        active_tests[test_id]["connection_names"] = connection_names
        active_tests[test_id]["connection_db_types"] = connection_db_types
        active_tests[test_id]["finished_at"] = finish_ts
        
        await streaming_callback.on_test_complete(summary)
        
    except TestCancelledError as e:
        cancel_message = str(e) or "Тест отменён пользователем"
        print(f"[TEST] Тест {test_id} отменён: {cancel_message}")
        active_tests[test_id]["status"] = "cancelled"
        active_tests[test_id]["error"] = cancel_message
        active_tests[test_id]["finished_at"] = _now_utc()

        await streaming_callback.drain_realtime_metrics()
        await streaming_callback.on_status_change("cancelled", cancel_message)

        if HISTORY_ENABLED and test_repository:
            try:
                finish_ts = start_ts + timedelta(seconds=(time.perf_counter() - start_time))
                await test_repository.update_test_run_status(
                    test_id,
                    'cancelled',
                    {"cancelled": True, "reason": cancel_message},
                    started_at=start_ts,
                    finished_at=finish_ts
                )
            except Exception:
                pass
    except Exception as e:
        print(f"[TEST] Ошибка выполнения теста {test_id}: {e}")
        import traceback
        traceback.print_exc()
        error_message = str(e)
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = error_message
        active_tests[test_id]["finished_at"] = _now_utc()
        
        await streaming_callback.drain_realtime_metrics()
        await streaming_callback.on_test_error(error_message)
        
        if HISTORY_ENABLED and test_repository:
            try:
                finish_ts = start_ts + timedelta(seconds=(time.perf_counter() - start_time))
                await test_repository.update_test_run_status(
                    test_id,
                    'failed',
                    {"error": error_message},
                    started_at=start_ts,
                    finished_at=finish_ts
                )
            except:
                pass
    finally:
        await test_tester.close()
        if test_id in active_tests:
            active_tests[test_id].pop("_task", None)
            active_tests[test_id].pop("_tester", None)
            active_tests[test_id].pop("_streaming_callback", None)


@router.post("/async/{test_id}/cancel")
async def cancel_async_test(test_id: str):
    """Запросить корректную отмену запущенного теста."""
    active_tests = get_active_tests()
    prune_active_tests(active_tests)
    test_info = active_tests.get(test_id)
    if not test_info:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")

    status = test_info.get("status")
    if status in TERMINAL_TEST_STATUSES:
        raise HTTPException(status_code=409, detail=f"Тест уже завершён (status={status})")

    if status != "cancelling":
        test_info["status"] = "cancelling"
        tester = test_info.get("_tester")
        if tester:
            tester.request_cancel()

    streaming_callback = test_info.get("_streaming_callback")
    if streaming_callback:
        await streaming_callback.on_status_change(
            "cancelling",
            "Остановка теста: завершаем текущие операции…",
        )
    else:
        await manager.send_status_update(
            TestStatusUpdate(
                test_id=test_id,
                status="cancelling",
                message="Остановка теста: завершаем текущие операции…",
                progress=0.0,
            )
        )

    return {
        "test_id": test_id,
        "status": "cancelling",
        "message": "Запрос на остановку принят",
    }


@router.get("/async/{test_id}")
async def get_async_test_status(test_id: str):
    """Получить статус асинхронного теста"""
    active_tests = get_active_tests()
    prune_active_tests(active_tests)
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    return _public_test_info(active_tests[test_id])


@router.get("/async/{test_id}/results")
async def get_async_test_results(test_id: str):
    """Получить результаты асинхронного теста"""
    active_tests = get_active_tests()
    prune_active_tests(active_tests)
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    test_info = active_tests[test_id]
    if test_info["status"] != "completed":
        message = test_info.get("error") or "Тест ещё не завершён"
        if test_info["status"] == "cancelled":
            message = test_info.get("error") or "Тест отменён пользователем"
        elif test_info["status"] == "cancelling":
            message = "Остановка теста: завершаем текущие операции…"
        return {
            "status": test_info["status"],
            "message": message,
            "error": test_info.get("error"),
            "connection_names": test_info.get("connection_names", {}),
            "connection_db_types": test_info.get("connection_db_types", {})
        }
    
    return {
        "status": "completed",
        "results": test_info.get("results", []),
        "summary": sanitize_test_summary(test_info.get("summary")) or {},
        "system_metrics": test_info.get("system_metrics", {}),
        "dbms_metrics": test_info.get("dbms_metrics", {}),
        "connection_names": test_info.get("connection_names", {}),
        "connection_db_types": test_info.get("connection_db_types", {})
    }
