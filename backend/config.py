"""
Конфигурация системы отката баз данных

Делегирует к backend.core.config для единого источника правды.
"""
from typing import Dict, Any

from backend.core.config import (
    RESTORE_CONFIG,
    get_restore_config,
    update_restore_config,
)

__all__ = ["RESTORE_CONFIG", "get_restore_config", "update_restore_config"]
