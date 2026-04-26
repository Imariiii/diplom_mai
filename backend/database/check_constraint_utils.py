"""
Утилиты нормализации CHECK-ограничений между разными SQL-диалектами.
"""
import re
from typing import Optional


def normalize_check_constraint(clause: Optional[str]) -> str:
    """Привести CHECK expression к стабильной форме для сравнения схем."""
    if not clause:
        return ""

    normalized = str(clause).strip().rstrip(";").lower()
    normalized = normalized.replace("`", "").replace('"', "")
    normalized = re.sub(r"\s+", " ", normalized)

    # information_schema разных СУБД по-разному оборачивает простые выражения.
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    normalized = re.sub(r"\s*>=\s*", " >= ", normalized)
    normalized = re.sub(r"\s*<=\s*", " <= ", normalized)
    normalized = re.sub(r"\s*(?<![<>!])=(?![=])\s*", " = ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    between_pattern = re.compile(
        r"\b([a-z_][a-z0-9_\.]*)\s+between\s+([^\s]+)\s+and\s+([^\s]+)"
    )
    normalized = between_pattern.sub(r"\1 >= \2 and \1 <= \3", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def is_redundant_not_null_check(clause: Optional[str]) -> bool:
    """Определить CHECK, который фактически дублирует NOT NULL."""
    normalized = normalize_check_constraint(clause)
    return bool(re.fullmatch(r"[a-z_][a-z0-9_\.]* is not null", normalized))
