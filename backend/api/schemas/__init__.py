"""
API схемы для системы нагрузочного тестирования
"""
from backend.api.schemas.test_schemas import (
    TestRequest,
    AsyncTestRequest,
)
from backend.api.schemas.connection_schemas import ConnectionSchemaResponse
from backend.api.schemas.profile_schemas import (
    ScenarioTemplateResponse,
    ScenarioTemplateCreateRequest,
    ScenarioTemplateUpdateRequest,
    ConnectionProfileAssignRequest,
    SchemaProfileCreateRequest,
    ScenarioBundleSaveRequest,
    ScenarioBundleCloneRequest,
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
    "ConnectionSchemaResponse",
    "ScenarioTemplateResponse",
    "ScenarioTemplateCreateRequest",
    "ScenarioTemplateUpdateRequest",
    "ConnectionProfileAssignRequest",
    "SchemaProfileCreateRequest",
    "ScenarioBundleSaveRequest",
    "ScenarioBundleCloneRequest",
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