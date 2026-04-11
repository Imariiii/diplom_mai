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
    GenerateScenariosRequest,
    GenerateScenariosResponse,
)
from backend.api.schemas.connection_schemas import ConnectionSchemaResponse
from backend.api.schemas.profile_schemas import (
    ScenarioTemplateResponse,
    ConnectionProfileAssignRequest,
    SchemaProfileCreateRequest,
    ScenarioBundleSummaryResponse,
    ProfileBundleGenerateRequest,
    SchemaProfileDetailResponse,
    ScenarioTemplateListResponse,
    SchemaProfileListResponse,
    SchemaProfileBundlesResponse,
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
    "GenerateScenariosRequest",
    "GenerateScenariosResponse",
    "ConnectionSchemaResponse",
    "ScenarioTemplateResponse",
    "ConnectionProfileAssignRequest",
    "SchemaProfileCreateRequest",
    "ScenarioBundleSummaryResponse",
    "ProfileBundleGenerateRequest",
    "SchemaProfileDetailResponse",
    "ScenarioTemplateListResponse",
    "SchemaProfileListResponse",
    "SchemaProfileBundlesResponse",
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