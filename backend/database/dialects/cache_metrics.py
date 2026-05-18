"""
Расчёт Cache Hit Ratio: raw engine-level delta и display verdict (hybrid model).
"""
from typing import Any, Dict, List, Optional

from backend.load_tester.sql_workload_classifier import (
    ACTIVITY_SCALAR_ONLY,
    ACTIVITY_METADATA_ONLY,
    ACTIVITY_USER_TABLE_READ,
    ACTIVITY_WRITE_WORKLOAD,
    ACTIVITY_MIXED_OR_UNKNOWN,
)


CACHE_STATUS_OK = "ok"
CACHE_STATUS_NO_ACTIVITY = "no_activity"
CACHE_STATUS_INVALID_COUNTER = "invalid_counter"
CACHE_STATUS_UNAVAILABLE = "unavailable"

CACHE_MODE_DELTA = "delta"
CACHE_COUNTER_POSTGRESQL = "postgresql_blks"
CACHE_COUNTER_POSTGRESQL_STATIO = "postgresql_statio_user"
CACHE_COUNTER_INNODB = "innodb_buffer_pool"

SCOPE_ENGINE_GLOBAL = "engine_global"
SCOPE_USER_RELATIONS = "user_relations"

MEANINGFULNESS_MEANINGFUL = "meaningful"
MEANINGFULNESS_NOT_MEANINGFUL = "not_meaningful_for_workload"
MEANINGFULNESS_LOW_ACTIVITY = "low_cache_activity"
MEANINGFULNESS_ENGINE_ONLY = "engine_activity_only"

# Минимальный знаменатель для интерпретации InnoDB ratio как workload-relevant
MIN_INNODB_READ_REQUESTS = 100
# Минимальный знаменатель для pg_statio (хотя бы одно обращение к странице user relation)
MIN_STATIO_BLOCKS = 1


def _safe_delta(end: Any, start: Any) -> Optional[float]:
    if end is None or start is None:
        return None
    try:
        return float(end) - float(start)
    except (TypeError, ValueError):
        return None


def _ratio_result(
    ratio: Optional[float],
    status: str,
    note: str,
    numerator: Optional[float] = None,
    denominator: Optional[float] = None,
    counter_source: Optional[str] = None,
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ratio": ratio,
        "status": status,
        "note": note,
        "numerator": numerator,
        "denominator": denominator,
        "counter_source": counter_source,
        "scope": scope,
    }


def compute_postgresql_cache_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    """Доля попаданий в shared buffers: delta(blks_hit) / (delta_hit + delta_read)."""
    d_hit = _safe_delta(end_counters.get("blks_hit"), start_counters.get("blks_hit"))
    d_read = _safe_delta(end_counters.get("blks_read"), start_counters.get("blks_read"))

    if d_hit is None or d_read is None:
        return _ratio_result(
            None,
            CACHE_STATUS_UNAVAILABLE,
            "Не удалось прочитать счётчики pg_stat_database (blks_hit/blks_read).",
            counter_source=CACHE_COUNTER_POSTGRESQL,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    if d_hit < 0 or d_read < 0:
        return _ratio_result(
            None,
            CACHE_STATUS_INVALID_COUNTER,
            "Отрицательная дельта счётчиков (возможен сброс статистики PostgreSQL).",
            numerator=d_hit,
            denominator=(d_hit or 0) + (d_read or 0),
            counter_source=CACHE_COUNTER_POSTGRESQL,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    denom = d_hit + d_read
    if denom <= 0:
        return _ratio_result(
            None,
            CACHE_STATUS_NO_ACTIVITY,
            "За прогон не было обращений к буферу страниц (blks_hit + blks_read = 0).",
            numerator=0.0,
            denominator=0.0,
            counter_source=CACHE_COUNTER_POSTGRESQL,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    ratio = round(100.0 * d_hit / denom, 4)
    return _ratio_result(
        ratio,
        CACHE_STATUS_OK,
        "Доля попаданий в shared buffers (engine-level) за прогон.",
        numerator=d_hit,
        denominator=denom,
        counter_source=CACHE_COUNTER_POSTGRESQL,
        scope=SCOPE_ENGINE_GLOBAL,
    )


def compute_postgresql_statio_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    """Workload-relevant ratio по pg_statio_user_tables/indexes."""
    d_hit = _safe_delta(
        end_counters.get("statio_blks_hit"), start_counters.get("statio_blks_hit")
    )
    d_read = _safe_delta(
        end_counters.get("statio_blks_read"), start_counters.get("statio_blks_read")
    )

    if d_hit is None or d_read is None:
        return _ratio_result(
            None,
            CACHE_STATUS_UNAVAILABLE,
            "Не удалось прочитать pg_statio_user_tables/indexes.",
            counter_source=CACHE_COUNTER_POSTGRESQL_STATIO,
            scope=SCOPE_USER_RELATIONS,
        )

    if d_hit < 0 or d_read < 0:
        return _ratio_result(
            None,
            CACHE_STATUS_INVALID_COUNTER,
            "Отрицательная дельта statio-счётчиков.",
            numerator=d_hit,
            denominator=(d_hit or 0) + (d_read or 0),
            counter_source=CACHE_COUNTER_POSTGRESQL_STATIO,
            scope=SCOPE_USER_RELATIONS,
        )

    denom = d_hit + d_read
    if denom < MIN_STATIO_BLOCKS:
        return _ratio_result(
            None,
            CACHE_STATUS_NO_ACTIVITY,
            "За прогон не было обращений к страницам пользовательских таблиц/индексов.",
            numerator=d_hit,
            denominator=denom,
            counter_source=CACHE_COUNTER_POSTGRESQL_STATIO,
            scope=SCOPE_USER_RELATIONS,
        )

    ratio = round(100.0 * d_hit / denom, 4) if denom > 0 else None
    return _ratio_result(
        ratio,
        CACHE_STATUS_OK,
        "Доля попаданий в кэш по пользовательским relation pages за прогон.",
        numerator=d_hit,
        denominator=denom,
        counter_source=CACHE_COUNTER_POSTGRESQL_STATIO,
        scope=SCOPE_USER_RELATIONS,
    )


def compute_innodb_cache_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    """InnoDB buffer pool hit ratio за интервал."""
    d_reads = _safe_delta(
        end_counters.get("innodb_buffer_pool_reads"),
        start_counters.get("innodb_buffer_pool_reads"),
    )
    d_requests = _safe_delta(
        end_counters.get("innodb_buffer_pool_read_requests"),
        start_counters.get("innodb_buffer_pool_read_requests"),
    )

    if d_reads is None or d_requests is None:
        return _ratio_result(
            None,
            CACHE_STATUS_UNAVAILABLE,
            "Не удалось прочитать счётчики InnoDB buffer pool.",
            counter_source=CACHE_COUNTER_INNODB,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    if d_reads < 0 or d_requests < 0:
        return _ratio_result(
            None,
            CACHE_STATUS_INVALID_COUNTER,
            "Отрицательная дельта счётчиков InnoDB.",
            numerator=d_reads,
            denominator=d_requests,
            counter_source=CACHE_COUNTER_INNODB,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    if d_requests <= 0:
        return _ratio_result(
            None,
            CACHE_STATUS_NO_ACTIVITY,
            "За прогон не было логических обращений к InnoDB buffer pool.",
            numerator=0.0,
            denominator=0.0,
            counter_source=CACHE_COUNTER_INNODB,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    if d_reads > d_requests:
        return _ratio_result(
            None,
            CACHE_STATUS_INVALID_COUNTER,
            "Аномалия счётчиков InnoDB: buffer_pool_reads > read_requests за прогон.",
            numerator=d_reads,
            denominator=d_requests,
            counter_source=CACHE_COUNTER_INNODB,
            scope=SCOPE_ENGINE_GLOBAL,
        )

    ratio = round((1.0 - (d_reads / d_requests)) * 100.0, 4)
    ratio = max(0.0, min(100.0, ratio))
    return _ratio_result(
        ratio,
        CACHE_STATUS_OK,
        "Доля попаданий в InnoDB buffer pool (engine-level) за прогон.",
        numerator=d_requests - d_reads,
        denominator=d_requests,
        counter_source=CACHE_COUNTER_INNODB,
        scope=SCOPE_ENGINE_GLOBAL,
    )


def compute_raw_engine_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    """Сырое engine-level ratio по типу СУБД."""
    if not start_counters or not end_counters:
        return _ratio_result(
            None,
            CACHE_STATUS_UNAVAILABLE,
            "Нет начальных или конечных счётчиков.",
        )

    has_pg = "blks_hit" in start_counters or "blks_hit" in end_counters
    has_innodb = (
        "innodb_buffer_pool_reads" in start_counters
        or "innodb_buffer_pool_reads" in end_counters
    )

    if has_pg:
        return compute_postgresql_cache_delta(start_counters, end_counters)
    if has_innodb:
        return compute_innodb_cache_delta(start_counters, end_counters)

    return _ratio_result(
        None,
        CACHE_STATUS_UNAVAILABLE,
        "Счётчики кэша для данной СУБД не настроены.",
    )


def compute_workload_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    """Workload-facing ratio (PostgreSQL statio; для InnoDB — engine global с отдельной оценкой meaningfulness)."""
    if "statio_blks_hit" in start_counters or "statio_blks_hit" in end_counters:
        return compute_postgresql_statio_delta(start_counters, end_counters)
    return _ratio_result(
        None,
        CACHE_STATUS_UNAVAILABLE,
        "Workload-relevant statio-счётчики недоступны для этой СУБД.",
        counter_source=None,
        scope=None,
    )


def evaluate_display_metric(
    raw_engine: Dict[str, Any],
    workload: Dict[str, Any],
    workload_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Выбрать, что показывать в UI, и оценить meaningfulness.

    Returns dict with display_value, display_status, display_note, meaningfulness, scope, source, denominator.
    """
    ctx = workload_context or {}
    activity = ctx.get("activity_class", ACTIVITY_MIXED_OR_UNKNOWN)

    raw_ratio = raw_engine.get("ratio")
    raw_status = raw_engine.get("status", CACHE_STATUS_UNAVAILABLE)
    workload_ratio = workload.get("ratio")
    workload_status = workload.get("status", CACHE_STATUS_UNAVAILABLE)
    workload_denom = workload.get("denominator") or 0
    engine_denom = raw_engine.get("denominator") or 0

    # PostgreSQL: предпочитаем user-relations metric для display
    if workload_status == CACHE_STATUS_OK and workload_denom >= MIN_STATIO_BLOCKS:
        return {
            "display_value": workload_ratio,
            "display_status": CACHE_STATUS_OK,
            "display_note": workload.get("note", ""),
            "meaningfulness": MEANINGFULNESS_MEANINGFUL,
            "scope": SCOPE_USER_RELATIONS,
            "source": workload.get("counter_source"),
            "denominator": workload_denom,
            "activity_class": activity,
        }

    # InnoDB / PG без statio activity: оценка по engine + activity class
    if activity in (ACTIVITY_SCALAR_ONLY, ACTIVITY_METADATA_ONLY):
        return {
            "display_value": None,
            "display_status": CACHE_STATUS_NO_ACTIVITY,
            "display_note": (
                "Запрос не обращается к пользовательским данным; "
                "метрика кэша для этого workload неинформативна."
            ),
            "meaningfulness": MEANINGFULNESS_NOT_MEANINGFUL,
            "scope": SCOPE_ENGINE_GLOBAL,
            "source": raw_engine.get("counter_source"),
            "denominator": engine_denom,
            "activity_class": activity,
            "raw_engine_ratio": raw_ratio,
            "raw_engine_status": raw_status,
        }

    if (
        raw_status == CACHE_STATUS_OK
        and engine_denom > 0
        and workload_status == CACHE_STATUS_NO_ACTIVITY
        and workload.get("scope") == SCOPE_USER_RELATIONS
    ):
        return {
            "display_value": None,
            "display_status": CACHE_STATUS_NO_ACTIVITY,
            "display_note": (
                "Была активность buffer pool на уровне engine, "
                "но не по пользовательским таблицам в окне измерения. "
                "Для сравнения сценариев используйте нагрузку с чтением таблиц."
            ),
            "meaningfulness": MEANINGFULNESS_ENGINE_ONLY,
            "scope": SCOPE_ENGINE_GLOBAL,
            "source": raw_engine.get("counter_source"),
            "denominator": engine_denom,
            "activity_class": activity,
            "raw_engine_ratio": raw_ratio,
            "raw_engine_status": raw_status,
        }

    if raw_status == CACHE_STATUS_OK and engine_denom >= MIN_INNODB_READ_REQUESTS:
        if activity in (ACTIVITY_USER_TABLE_READ, ACTIVITY_WRITE_WORKLOAD, ACTIVITY_MIXED_OR_UNKNOWN):
            return {
                "display_value": raw_ratio,
                "display_status": CACHE_STATUS_OK,
                "display_note": (
                    f"{raw_engine.get('note', '')} "
                    "Внимание: метрика engine-level и включает фоновую активность СУБД."
                ),
                "meaningfulness": MEANINGFULNESS_MEANINGFUL,
                "scope": SCOPE_ENGINE_GLOBAL,
                "source": raw_engine.get("counter_source"),
                "denominator": engine_denom,
                "activity_class": activity,
                "raw_engine_ratio": raw_ratio,
                "raw_engine_status": raw_status,
            }

    if raw_status in (CACHE_STATUS_NO_ACTIVITY, CACHE_STATUS_UNAVAILABLE):
        return {
            "display_value": None,
            "display_status": raw_status,
            "display_note": raw_engine.get("note", "Нет данных для расчёта cache hit ratio за прогон."),
            "meaningfulness": MEANINGFULNESS_LOW_ACTIVITY,
            "scope": SCOPE_ENGINE_GLOBAL,
            "source": raw_engine.get("counter_source"),
            "denominator": engine_denom,
            "activity_class": activity,
            "raw_engine_ratio": raw_ratio,
            "raw_engine_status": raw_status,
        }

    if raw_status == CACHE_STATUS_INVALID_COUNTER:
        return {
            "display_value": None,
            "display_status": CACHE_STATUS_INVALID_COUNTER,
            "display_note": raw_engine.get("note", ""),
            "meaningfulness": MEANINGFULNESS_NOT_MEANINGFUL,
            "scope": SCOPE_ENGINE_GLOBAL,
            "source": raw_engine.get("counter_source"),
            "denominator": engine_denom,
            "activity_class": activity,
            "raw_engine_ratio": raw_ratio,
            "raw_engine_status": raw_status,
        }

    if engine_denom > 0 and engine_denom < MIN_INNODB_READ_REQUESTS:
        return {
            "display_value": None,
            "display_status": CACHE_STATUS_NO_ACTIVITY,
            "display_note": (
                "Слишком мало обращений к buffer pool за прогон для устойчивой интерпретации."
            ),
            "meaningfulness": MEANINGFULNESS_LOW_ACTIVITY,
            "scope": SCOPE_ENGINE_GLOBAL,
            "source": raw_engine.get("counter_source"),
            "denominator": engine_denom,
            "activity_class": activity,
            "raw_engine_ratio": raw_ratio,
            "raw_engine_status": raw_status,
        }

    return {
        "display_value": None,
        "display_status": CACHE_STATUS_UNAVAILABLE,
        "display_note": "Не удалось определить отображаемую метрику кэша.",
        "meaningfulness": MEANINGFULNESS_NOT_MEANINGFUL,
        "scope": SCOPE_ENGINE_GLOBAL,
        "source": None,
        "denominator": 0,
        "activity_class": activity,
        "raw_engine_ratio": raw_ratio,
        "raw_engine_status": raw_status,
    }


def build_hybrid_cache_metrics(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
    workload_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Построить полный hybrid-контракт cache metrics для сохранения в dbms_metrics."""
    raw_engine = compute_raw_engine_delta(start_counters, end_counters)
    workload = compute_workload_delta(start_counters, end_counters)
    display = evaluate_display_metric(raw_engine, workload, workload_context)

    return {
        "cache_hit_ratio": display["display_value"],
        "buffer_pool_hit_ratio": display["display_value"],
        "cache_hit_ratio_mode": CACHE_MODE_DELTA,
        "buffer_pool_hit_ratio_mode": CACHE_MODE_DELTA,
        "cache_hit_ratio_status": display["display_status"] or CACHE_STATUS_UNAVAILABLE,
        "buffer_pool_hit_ratio_status": display["display_status"] or CACHE_STATUS_UNAVAILABLE,
        "cache_hit_ratio_note": display["display_note"],
        "buffer_pool_hit_ratio_note": display["display_note"],
        "cache_hit_ratio_raw": raw_engine["ratio"],
        "cache_hit_ratio_raw_status": raw_engine["status"],
        "cache_hit_ratio_raw_note": raw_engine["note"],
        "cache_hit_ratio_display_value": display["display_value"],
        "cache_hit_ratio_display_status": display["display_status"],
        "cache_hit_ratio_meaningfulness": display["meaningfulness"],
        "cache_hit_ratio_scope": display["scope"] or SCOPE_ENGINE_GLOBAL,
        "cache_hit_ratio_source": display["source"],
        "cache_hit_ratio_denominator": display["denominator"],
        "cache_hit_ratio_activity_class": display["activity_class"],
        "cache_hit_ratio_numerator": raw_engine.get("numerator"),
        "cache_hit_ratio_workload_ratio": workload.get("ratio"),
        "cache_hit_ratio_workload_status": workload.get("status"),
        "cache_counter_source": raw_engine.get("counter_source"),
    }


def apply_hybrid_cache_to_metrics(
    metrics: Dict[str, Any],
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
    workload_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Записать hybrid cache metrics в словарь (финальный снимок или live preview)."""
    hybrid = build_hybrid_cache_metrics(start_counters, end_counters, workload_context)
    metrics.update(hybrid)


def merge_running_cache_hit(
    metrics: Dict[str, Any],
    measurement_start: Dict[str, Any],
    current_counters: Dict[str, Any],
    workload_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Realtime: только счётчики, без тяжёлого collect_dbms_metrics."""
    hybrid = build_hybrid_cache_metrics(
        measurement_start, current_counters, workload_context
    )
    metrics.update(hybrid)


# Обратная совместимость
def compute_cache_hit_delta(
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> Dict[str, Any]:
    return compute_raw_engine_delta(start_counters, end_counters)


def apply_cache_hit_delta_to_metrics(
    metrics: Dict[str, Any],
    start_counters: Dict[str, Any],
    end_counters: Dict[str, Any],
) -> None:
    apply_hybrid_cache_to_metrics(metrics, start_counters, end_counters, workload_context=None)
