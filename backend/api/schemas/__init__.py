"""
API схемы для системы нагрузочного тестирования
"""
from backend.api.schemas.test_schemas import (
    TestRequest,
    AsyncTestRequest,
    TestScenario,
)
from backend.api.schemas.scenario_schemas import (
    ScenarioParamCreate,
    ScenarioParamUpdate,
    ScenarioParamResponse,
    ScenarioIndexCreate,
    ScenarioIndexUpdate,
    ScenarioIndexResponse,
    ScenarioQueryCreate,
    ScenarioQueryUpdate,
    ScenarioQueryResponse,
    TestScenarioCreate,
    TestScenarioUpdate,
    TestScenarioResponse,
    TestScenarioListResponse,
    CloneScenarioRequest,
)
from backend.api.schemas.backup_schemas import (
    BackupRequest,
    BackupResponse,
    RestoreRequest,
    RestoreResponse,
    CleanupResponse,
    EstimateResponse,
    RestoreSettings,
)
from backend.api.schemas.settings_schemas import (
    SettingsResponse,
    SettingsUpdateRequest,
)

__all__ = [
    # Test schemas
    "TestRequest",
    "AsyncTestRequest",
    "TestScenario",
    # Scenario schemas
    "ScenarioParamCreate",
    "ScenarioParamUpdate",
    "ScenarioParamResponse",
    "ScenarioIndexCreate",
    "ScenarioIndexUpdate",
    "ScenarioIndexResponse",
    "ScenarioQueryCreate",
    "ScenarioQueryUpdate",
    "ScenarioQueryResponse",
    "TestScenarioCreate",
    "TestScenarioUpdate",
    "TestScenarioResponse",
    "TestScenarioListResponse",
    "CloneScenarioRequest",
    # Backup schemas
    "BackupRequest",
    "BackupResponse",
    "RestoreRequest",
    "RestoreResponse",
    "CleanupResponse",
    "EstimateResponse",
    "RestoreSettings",
    # Settings schemas
    "SettingsResponse",
    "SettingsUpdateRequest",
]