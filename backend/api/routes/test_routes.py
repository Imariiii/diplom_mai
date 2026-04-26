"""
API роуты для выполнения тестов
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, List
import uuid
import asyncio

from backend.api.schemas import AsyncTestRequest
from backend.database.scenario_bundle_resolver import ScenarioBundleResolver
from backend.database.scenario_bundle_validator import ScenarioBundleValidator
from backend.load_tester.tester import LoadTester
from backend.websocket_manager import manager, TestStreamingCallback

router = APIRouter(prefix="/test", tags=["test"])


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


def _build_bundle_config_snapshot(bundle: Dict) -> Dict:
    """Собрать bundle snapshot для истории и comparison."""
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
        "queries": bundle.get("queries", []),
        "indexes": bundle.get("indexes", []),
    }


@router.post("/async")
async def run_async_test(request: AsyncTestRequest, background_tasks: BackgroundTasks):
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

    from backend.initialize import HISTORY_ENABLED, test_repository
    
    test_id = str(uuid.uuid4())
    test_name = request.test_name or f"Тест {test_id}"
    
    active_tests = get_active_tests()
    
    # Сохраняем информацию о тесте
    active_tests[test_id] = {
        "id": test_id,
        "name": test_name,
        "status": "pending",
        "config": request.model_dump(),
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
    
    # Запускаем тест в фоне
    background_tasks.add_task(
        run_test_with_streaming,
        test_id,
        request
    )
    
    return {
        "test_id": test_id,
        "name": test_name,
        "status": "pending",
        "websocket_url": f"/ws/test/{test_id}",
        "message": "Тест запущен. Подключитесь к WebSocket для получения обновлений."
    }


async def run_test_with_streaming(test_id: str, request: AsyncTestRequest):
    """Фоновая задача для выполнения теста с WebSocket стримингом"""
    from datetime import datetime, timedelta, timezone
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
    
    from backend.core.config import settings
    
    test_tester = LoadTester(connection_repo=connection_repository)
    test_tester.set_streaming_callback(streaming_callback)
    test_tester.set_backup_callback(streaming_callback.on_backup_status)
    test_tester.auto_restore = settings.restore.auto_restore
    
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
        except Exception as e:
            print(f"[TEST] Ошибка загрузки подключений: {e}")
            import traceback
            traceback.print_exc()
            active_tests[test_id]["status"] = "failed"
            active_tests[test_id]["error"] = f"Ошибка загрузки подключений: {e}"
            await streaming_callback.on_test_error(f"Ошибка загрузки подключений: {e}")
            return
    elif not db_keys:
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = "Не указаны connection_ids или db_types"
        await streaming_callback.on_test_error("Не указаны connection_ids или db_types")
        return
    
    if not db_keys:
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = "Не удалось определить тип БД"
        await streaming_callback.on_test_error("Не удалось определить тип БД")
        return
    
    print(f"[TEST] Запуск теста с db_keys={db_keys}, connection_names={connection_names}")
    print(
        f"[TEST] Параметры: итераций={request.iterations}, VU={request.virtual_users}, "
        f"warmup={request.warmup_time}s, индексы={request.use_indexes}"
    )
    
    try:
        active_tests[test_id]["status"] = "running"
        await streaming_callback.on_test_start()

        dbms_metric_start_counters = {}
        for db_key in db_keys:
            streaming_callback.ensure_dbms_runtime_stats(db_key)
            dbms_metric_start_counters[db_key] = await test_tester.get_dbms_metric_counters(db_key)
        
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
            queries_count = len(resolved_bundle.get("queries", []))
            print(
                f"[TEST] Разрешён bundle: {resolved_bundle['name']!r} "
                f"(профиль: {resolved['schema_profile_name']!r}), запросов: {queries_count}"
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
                    "Preflight-проверка scenario bundle не пройдена: "
                    + "; ".join(preflight.get("errors", []))
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
            await streaming_callback.on_test_error(error_msg)
            return

        await streaming_callback.on_status_change(
            "running",
            "Финализация результатов: сбор метрик и сохранение…",
        )

        end_time = time.perf_counter()
        actual_duration = end_time - start_time
        finish_ts = start_ts + timedelta(seconds=actual_duration)

        system_metrics = {}
        dbms_metrics = {}
        for db_key in db_keys:
            try:
                system_metrics[db_key] = await test_tester.get_system_metrics(db_key)
                latest_dbms_metrics = await test_tester.get_dbms_metrics(db_key)
                dbms_metric_end_counters = await test_tester.get_dbms_metric_counters(db_key)
                dbms_metrics[db_key] = test_tester.build_final_dbms_metrics(
                    db_key=db_key,
                    latest_metrics=latest_dbms_metrics,
                    start_counters=dbms_metric_start_counters.get(db_key, {}),
                    end_counters=dbms_metric_end_counters,
                    runtime_stats=streaming_callback.get_dbms_runtime_stats(db_key),
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
        
        summary = {
            'total_transactions': total_transactions,
            'overall_tps': total_transactions / actual_duration if actual_duration > 0 else 0,
            'total_duration': actual_duration
        }
        print(
            f"[TEST] Тест {test_id} завершён за {actual_duration:.1f}с. "
            f"Транзакций: {total_transactions}, TPS: {summary['overall_tps']:.1f}"
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
        
        # Добавляем db_name в результаты для отображения
        for result in results:
            if 'comparison' in result:
                for db_key, stats in result.get('comparison', {}).items():
                    stats['connection_key'] = db_key
                    stats['db_name'] = connection_names.get(db_key, db_key)
            elif 'db_key' in result:
                result['db_name'] = connection_names.get(result['db_key'], result['db_key'])

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
        
        await streaming_callback.on_test_complete(summary)
        
    except Exception as e:
        print(f"[TEST] Ошибка выполнения теста {test_id}: {e}")
        import traceback
        traceback.print_exc()
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["error"] = str(e)
        
        await streaming_callback.on_test_error(str(e))
        
        if HISTORY_ENABLED and test_repository:
            try:
                finish_ts = start_ts + timedelta(seconds=(time.perf_counter() - start_time))
                await test_repository.update_test_run_status(
                    test_id,
                    'failed',
                    None,
                    started_at=start_ts,
                    finished_at=finish_ts
                )
            except:
                pass
    finally:
        await test_tester.close()


@router.get("/async/{test_id}")
async def get_async_test_status(test_id: str):
    """Получить статус асинхронного теста"""
    active_tests = get_active_tests()
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    return active_tests[test_id]


@router.get("/async/{test_id}/results")
async def get_async_test_results(test_id: str):
    """Получить результаты асинхронного теста"""
    active_tests = get_active_tests()
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail=f"Тест {test_id} не найден")
    
    test_info = active_tests[test_id]
    if test_info["status"] != "completed":
        return {
            "status": test_info["status"],
            "message": "Тест ещё не завершён"
        }
    
    return {
        "status": "completed",
        "results": test_info.get("results", []),
        "summary": test_info.get("summary", {}),
        "system_metrics": test_info.get("system_metrics", {}),
        "dbms_metrics": test_info.get("dbms_metrics", {}),
        "connection_names": test_info.get("connection_names", {}),
        "connection_db_types": test_info.get("connection_db_types", {})
    }
