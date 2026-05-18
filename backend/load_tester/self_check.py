"""
Самопроверка корректности агрегированных метрик нагрузочного теста.
"""
from typing import Any, Dict, List, Optional


def verify_littles_law(
    virtual_users: int,
    avg_latency_sec: float,
    throughput_rps: float,
    tolerance: float = 0.3,
) -> Dict[str, Any]:
    """Проверить согласованность метрик через закон Литтла."""
    if virtual_users <= 0:
        return {
            "valid": False,
            "reason": "invalid_virtual_users",
            "computed_concurrency": 0.0,
            "expected_concurrency": virtual_users,
            "ratio": None,
            "tolerance": tolerance,
            "warning": "Невозможно проверить закон Литтла: virtual_users <= 0",
        }

    if throughput_rps <= 0 or avg_latency_sec <= 0:
        return {
            "valid": False,
            "reason": "zero_metrics",
            "computed_concurrency": 0.0,
            "expected_concurrency": virtual_users,
            "ratio": 0.0,
            "tolerance": tolerance,
            "warning": "Недостаточно данных для проверки закона Литтла: throughput или latency равны нулю",
        }

    computed_sql_concurrency = throughput_rps * avg_latency_sec
    ratio = computed_sql_concurrency / float(virtual_users)
    is_consistent = ratio <= (1.0 + tolerance)

    return {
        "valid": is_consistent,
        "reason": None if is_consistent else "concurrency_mismatch",
        "computed_concurrency": computed_sql_concurrency,
        "computed_sql_concurrency": computed_sql_concurrency,
        "expected_concurrency": virtual_users,
        "ratio": ratio,
        "tolerance": tolerance,
        "warning": None if is_consistent else (
            f"Закон Литтла нарушен: вычислено N={computed_sql_concurrency:.2f}, ожидалось {virtual_users}"
        ),
    }


def _optional_float(stats: Dict[str, Any], key: str) -> Optional[float]:
    value = stats.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(stats: Dict[str, Any], key: str) -> Optional[int]:
    value = stats.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def cross_validate_metrics(stats: Dict[str, Any]) -> List[str]:
    """Выполнить набор sanity-check для собранных метрик."""
    warnings: List[str] = []

    successful = _optional_int(stats, "successful") or 0
    failed = _optional_int(stats, "failed") or 0
    actual_total = successful + failed

    iterations = _optional_int(stats, "iterations")
    virtual_users = _optional_int(stats, "virtual_users")
    expected_total = None
    if iterations is not None and virtual_users is not None:
        expected_total = iterations * virtual_users

    if expected_total is not None and actual_total != expected_total:
        warnings.append(
            f"Количество результатов не совпадает с ожидаемым: actual={actual_total}, expected={expected_total}"
        )

    error_rate = _optional_float(stats, "error_rate")
    if error_rate is not None and actual_total > 0:
        expected_error_rate = (failed / actual_total) * 100.0
        if abs(error_rate - expected_error_rate) > 0.01:
            warnings.append(
                f"Неконсистентный error_rate: actual={error_rate:.4f}, expected={expected_error_rate:.4f}"
            )

    min_time = _optional_float(stats, "min_time_ms")
    avg_time = _optional_float(stats, "avg_time_ms")
    max_time = _optional_float(stats, "max_time_ms")
    p50 = _optional_float(stats, "p50_time_ms")
    p95 = _optional_float(stats, "p95_time_ms")
    p99 = _optional_float(stats, "p99_time_ms")

    if None not in (min_time, p50, p95, p99, max_time):
        if not (min_time <= p50 <= p95 <= p99 <= max_time):
            warnings.append("Перцентили выходят из ожидаемого монотонного порядка")

    if None not in (min_time, avg_time, max_time):
        if not (min_time <= avg_time <= max_time):
            warnings.append("Среднее время отклика выходит за пределы min/max")

    std_dev = _optional_float(stats, "std_dev_ms")
    if std_dev is not None and std_dev < 0:
        warnings.append("std_dev_ms не может быть отрицательным")

    throughput = _optional_float(stats, "throughput")
    if throughput is None:
        throughput = _optional_float(stats, "tps")
    if successful > 0 and throughput is not None and throughput <= 0:
        warnings.append("throughput должен быть положительным при наличии успешных запросов")

    attempt_rate = _optional_float(stats, "attempt_rate")
    if attempt_rate is None:
        attempt_rate = _optional_float(stats, "completed_tps")
    actual_total = successful + failed
    if actual_total > 0 and attempt_rate is not None and attempt_rate <= 0:
        warnings.append("attempt_rate должен быть положительным при наличии попыток")

    return warnings
