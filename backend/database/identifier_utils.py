"""
Утилиты для безопасных SQL-идентификаторов.
"""
import hashlib


SAFE_IDENTIFIER_MAX_LENGTH = 63


def shorten_identifier(identifier: str, max_length: int = SAFE_IDENTIFIER_MAX_LENGTH) -> str:
    """Сократить идентификатор с устойчивым hash suffix."""
    if len(identifier) <= max_length:
        return identifier

    digest = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:10]
    prefix_length = max(1, max_length - len(digest) - 1)
    return f"{identifier[:prefix_length].rstrip('_')}_{digest}"
