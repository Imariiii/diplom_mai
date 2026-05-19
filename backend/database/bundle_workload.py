"""
Вспомогательные функции для query- и transaction-level bundle.
"""
from typing import Any, Dict, List


def get_bundle_workload_mode(bundle: Dict[str, Any]) -> str:
    """Вернуть режим нагрузки bundle (query по умолчанию для обратной совместимости)."""
    mode = (bundle.get("workload_mode") or "query").strip().lower()
    return mode if mode in {"query", "transaction"} else "query"


def get_primary_rate_unit(workload_mode: str) -> str:
    """Единица primary throughput для режима нагрузки."""
    return "tps" if workload_mode == "transaction" else "qps"


def collect_bundle_sql_templates(bundle: Dict[str, Any]) -> List[str]:
    """Собрать все SQL-шаблоны bundle для backup/restore и классификации нагрузки."""
    mode = get_bundle_workload_mode(bundle)
    sql_list: List[str] = []
    if mode == "transaction":
        for transaction in bundle.get("transactions", []) or []:
            for step in transaction.get("steps", []) or []:
                template = step.get("sql_template")
                if template:
                    sql_list.append(template)
    else:
        for query in bundle.get("queries", []) or []:
            template = query.get("sql_template")
            if template:
                sql_list.append(template)
    return sql_list


def collect_param_refs_for_cache(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Собрать конфиги random_from_table для предзагрузки кэша."""
    mode = get_bundle_workload_mode(bundle)
    refs: List[Dict[str, Any]] = []
    if mode == "transaction":
        for transaction in bundle.get("transactions", []) or []:
            refs.extend(transaction.get("params", []) or [])
    else:
        for query in bundle.get("queries", []) or []:
            refs.extend(query.get("params", []) or [])
    return refs
