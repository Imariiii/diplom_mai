"""
Классификация SQL-нагрузки для оценки meaningfulness cache hit ratio.
"""
import re
from typing import Any, Dict, List, Optional


ACTIVITY_SCALAR_ONLY = "scalar_only"
ACTIVITY_METADATA_ONLY = "metadata_only"
ACTIVITY_USER_TABLE_READ = "user_table_read"
ACTIVITY_WRITE_WORKLOAD = "write_workload"
ACTIVITY_MIXED_OR_UNKNOWN = "mixed_or_unknown"

_SCALAR_PATTERN = re.compile(
    r"^\s*SELECT\s+(?:DISTINCT\s+)?(?:\d+|NULL)\s*(?:AS\s+\w+)?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_METADATA_PATTERNS = [
    re.compile(r"\binformation_schema\b", re.IGNORECASE),
    re.compile(r"\bpg_catalog\b", re.IGNORECASE),
    re.compile(r"\bpg_stat_\w+\b", re.IGNORECASE),
    re.compile(r"\bperformance_schema\b", re.IGNORECASE),
    re.compile(r"\bSHOW\s+(GLOBAL\s+)?STATUS\b", re.IGNORECASE),
    re.compile(r"\bSHOW\s+PROCESSLIST\b", re.IGNORECASE),
    re.compile(r"\bSHOW\s+ENGINE\b", re.IGNORECASE),
]

_WRITE_PATTERN = re.compile(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)
_READ_FROM_PATTERN = re.compile(r"\bFROM\s+[\w.\"`]+\b", re.IGNORECASE)


def classify_workload_sql(sql: Optional[str], sql_list: Optional[List[str]] = None) -> str:
    """
    Классифицировать нагрузку по SQL.

    Returns:
        scalar_only | metadata_only | user_table_read | write_workload | mixed_or_unknown
    """
    statements: List[str] = []
    if sql_list:
        statements.extend(s for s in sql_list if s and str(s).strip())
    elif sql:
        statements.append(sql)

    if not statements:
        return ACTIVITY_MIXED_OR_UNKNOWN

    classes = [_classify_single(s) for s in statements]
    if all(c == ACTIVITY_SCALAR_ONLY for c in classes):
        return ACTIVITY_SCALAR_ONLY
    if all(c == ACTIVITY_METADATA_ONLY for c in classes):
        return ACTIVITY_METADATA_ONLY
    if any(c == ACTIVITY_WRITE_WORKLOAD for c in classes):
        return ACTIVITY_WRITE_WORKLOAD if len(set(classes)) == 1 else ACTIVITY_MIXED_OR_UNKNOWN
    if all(c == ACTIVITY_USER_TABLE_READ for c in classes):
        return ACTIVITY_USER_TABLE_READ
    if ACTIVITY_USER_TABLE_READ in classes and ACTIVITY_SCALAR_ONLY in classes:
        return ACTIVITY_USER_TABLE_READ
    return ACTIVITY_MIXED_OR_UNKNOWN


def _classify_single(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        return ACTIVITY_MIXED_OR_UNKNOWN

    for pat in _METADATA_PATTERNS:
        if pat.search(cleaned):
            return ACTIVITY_METADATA_ONLY

    if _SCALAR_PATTERN.match(cleaned):
        return ACTIVITY_SCALAR_ONLY

    if _WRITE_PATTERN.search(cleaned):
        return ACTIVITY_WRITE_WORKLOAD

    if _READ_FROM_PATTERN.search(cleaned):
        return ACTIVITY_USER_TABLE_READ

    if re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        return ACTIVITY_USER_TABLE_READ

    return ACTIVITY_MIXED_OR_UNKNOWN


def workload_context_from_test(
    custom_sql: Optional[str] = None,
    scenario_queries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Собрать контекст workload для evaluator."""
    activity = classify_workload_sql(custom_sql, scenario_queries)
    return {
        "activity_class": activity,
        "custom_sql": custom_sql,
        "scenario_query_count": len(scenario_queries or []),
    }
