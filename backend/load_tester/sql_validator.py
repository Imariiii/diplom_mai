"""
Валидация и санитизация пользовательских SQL-запросов.

Разрешены только безопасные операции чтения/записи данных (DML).
Запрещены DDL-операции, административные команды и опасные конструкции.
"""
import re
from typing import Tuple, List

_FORBIDDEN_KEYWORDS = [
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bSET\b\s+(GLOBAL|SESSION|@@)",
    r"\bLOAD\b\s+DATA",
    r"\bINTO\s+OUTFILE\b",
    r"\bINTO\s+DUMPFILE\b",
    r"\bSHUTDOWN\b",
    r"\bKILL\b",
    r"\bRENAME\b",
    r"\bLOCK\b\s+TABLE",
    r"\bUNLOCK\b\s+TABLE",
    r"\bFLUSH\b",
    r"\bRESET\b",
    r"\bPURGE\b",
    r"\bCALL\b",
    r"\bEXEC(UTE)?\b",
    r"\bPREPARE\b",
    r"\bDEALLOCATE\b",
    r"\bDECLARE\b",
    r"\bCOPY\b",
    r"\bpg_sleep\b",
    r"\bSLEEP\s*\(",
    r"\bBENCHMARK\s*\(",
    r"\bsystem\s*\(",
    r";\s*\S",  # multiple statements
]

_FORBIDDEN_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _FORBIDDEN_KEYWORDS]

_ALLOWED_PREFIXES = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|EXPLAIN)\b",
    re.IGNORECASE,
)

_COMMENT_PATTERNS = [
    re.compile(r"/\*.*?\*/", re.DOTALL),   # block comments
    re.compile(r"--[^\n]*"),                # line comments
]


def validate_custom_sql(sql: str) -> Tuple[bool, List[str]]:
    """
    Validate a user-provided SQL string.

    Returns (is_valid, list_of_error_messages).
    An empty error list means the query is valid.
    """
    errors: List[str] = []

    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return False, ["SQL-запрос не может быть пустым"]

    cleaned = stripped
    for pat in _COMMENT_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    cleaned = cleaned.strip()

    if not _ALLOWED_PREFIXES.match(cleaned):
        errors.append(
            "Запрос должен начинаться с SELECT, INSERT, UPDATE, DELETE, WITH или EXPLAIN"
        )

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(cleaned):
            match_text = pattern.pattern.replace(r"\b", "").replace(r"\s+", " ")
            errors.append(f"Запрещённая конструкция: {match_text}")

    return len(errors) == 0, errors
