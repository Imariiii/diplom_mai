"""
API роуты для системы нагрузочного тестирования
"""
from backend.api.routes import test_routes
from backend.api.routes import scenario_routes
from backend.api.routes import database_state_routes
from backend.api.routes import history_routes
from backend.api.routes import settings_routes
from backend.api.routes import comparison_routes
from backend.api.routes import profile_routes

__all__ = [
    "test_routes",
    "scenario_routes",
    "database_state_routes",
    "history_routes",
    "settings_routes",
    "comparison_routes",
    "profile_routes",
]
