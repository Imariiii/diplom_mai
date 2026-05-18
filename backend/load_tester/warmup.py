"""
Политика и метаданные фазы прогрева нагрузочного теста.
"""
from typing import Any, Dict, Tuple


WARMUP_MODE_ACTIVE = "active_workload"
WARMUP_CONCURRENCY_MATCH = "match_measurement"
WARMUP_PLACEMENT_AFTER_PREPARE = "after_prepare_before_measurement"
WARMUP_PROFILE_STEADY = "steady"
WARMUP_PROFILE_RAMP_HOLD = "ramp_then_hold"


def compute_ramp_hold_seconds(warmup_time: int) -> Tuple[int, int, str]:
    """
    Разбить warmup_time на ramp и hold.

    Returns:
        (ramp_seconds, hold_seconds, warmup_profile)
    """
    if warmup_time <= 0:
        return 0, 0, WARMUP_PROFILE_STEADY
    if warmup_time < 3:
        return 0, warmup_time, WARMUP_PROFILE_STEADY
    ramp = min(max(1, int(warmup_time * 0.15)), warmup_time - 1)
    hold = warmup_time - ramp
    return ramp, hold, WARMUP_PROFILE_RAMP_HOLD


def build_warmup_metadata(warmup_time: int) -> Dict[str, Any]:
    """Метаданные прогрева для сохранения в config прогона."""
    ramp, hold, profile = compute_ramp_hold_seconds(warmup_time)
    return {
        "warmup_mode": WARMUP_MODE_ACTIVE,
        "warmup_concurrency_mode": WARMUP_CONCURRENCY_MATCH,
        "warmup_placement": WARMUP_PLACEMENT_AFTER_PREPARE,
        "warmup_profile": profile,
        "warmup_excluded_from_metrics": True,
        "warmup_ramp_seconds": ramp,
        "warmup_hold_seconds": hold,
    }


def merge_warmup_run_stats(
    metadata: Dict[str, Any],
    per_db_stats: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Агрегировать статистику прогрева по БД в config metadata."""
    merged = dict(metadata)
    if not per_db_stats:
        return merged
    total_attempted = sum(int(s.get("warmup_attempted_requests", 0) or 0) for s in per_db_stats.values())
    total_failed = sum(int(s.get("warmup_failed_requests", 0) or 0) for s in per_db_stats.values())
    total_ok = sum(int(s.get("warmup_successful_requests", 0) or 0) for s in per_db_stats.values())
    merged["warmup_attempted_requests"] = total_attempted
    merged["warmup_failed_requests"] = total_failed
    merged["warmup_successful_requests"] = total_ok
    merged["warmup_completed"] = all(s.get("warmup_completed", False) for s in per_db_stats.values()) if per_db_stats else True
    merged["warmup_per_db"] = per_db_stats
    return merged
