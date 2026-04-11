"""
API роуты для logical templates, schema profiles и profile bundles.
"""
from fastapi import APIRouter, HTTPException

from backend.api.schemas.profile_schemas import (
    ProfileBundleGenerateRequest,
    ScenarioTemplateListResponse,
    SchemaProfileBundlesResponse,
    SchemaProfileCreateRequest,
    SchemaProfileDetailResponse,
    SchemaProfileListResponse,
)
from backend.api.schemas.connection_schemas import SchemaProfileSummaryResponse
from backend.database.scenario_generator import ScenarioGenerator
from backend import initialize

router = APIRouter(prefix="/api/schema-profiles", tags=["schema-profiles"])


def get_profile_repository():
    if not initialize.profile_repository:
        raise HTTPException(status_code=503, detail="ProfileRepository не настроен")
    return initialize.profile_repository


def get_bundle_repository():
    if not initialize.scenario_bundle_repository:
        raise HTTPException(status_code=503, detail="ScenarioBundleRepository не настроен")
    return initialize.scenario_bundle_repository


def get_connection_repository():
    if not initialize.connection_repository:
        raise HTTPException(status_code=503, detail="ConnectionRepository не настроен")
    return initialize.connection_repository


@router.get("/templates", response_model=ScenarioTemplateListResponse)
async def list_scenario_templates():
    """Получить список logical templates."""
    profile_repo = get_profile_repository()
    templates = await profile_repo.list_templates()
    return ScenarioTemplateListResponse(
        templates=[template.to_dict() for template in templates]
    )


@router.get("", response_model=SchemaProfileListResponse)
async def list_schema_profiles():
    """Получить список schema profiles."""
    profile_repo = get_profile_repository()
    profiles = await profile_repo.list_profiles()
    return SchemaProfileListResponse(
        profiles=[SchemaProfileSummaryResponse(**profile.to_dict()) for profile in profiles]
    )


@router.post("", response_model=SchemaProfileSummaryResponse, status_code=201)
async def create_schema_profile(request: SchemaProfileCreateRequest):
    """Создать новый профиль схемы."""
    profile_repo = get_profile_repository()
    existing = await profile_repo.get_profile_by_name(request.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Профиль '{request.name}' уже существует")

    profile = await profile_repo.create_profile(
        name=request.name,
        description=request.description,
        reference_connection_id=request.reference_connection_id,
        is_builtin=False,
    )
    return SchemaProfileSummaryResponse(**profile.to_dict())


@router.get("/{profile_id}", response_model=SchemaProfileDetailResponse)
async def get_schema_profile(profile_id: str):
    """Получить профиль и связанные bundle'ы."""
    profile_repo = get_profile_repository()
    bundle_repo = get_bundle_repository()
    profile = await profile_repo.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    bundles = await bundle_repo.list_bundles(schema_profile_id=profile_id)
    return SchemaProfileDetailResponse(
        **profile.to_dict(),
        bundles=[bundle.to_dict() for bundle in bundles],
    )


@router.post("/{profile_id}/bundles/generate", response_model=SchemaProfileBundlesResponse)
async def generate_profile_bundles(profile_id: str, request: ProfileBundleGenerateRequest):
    """Сгенерировать канонические bundles по эталонному подключению профиля."""
    profile_repo = get_profile_repository()
    bundle_repo = get_bundle_repository()
    connection_repo = get_connection_repository()

    profile = await profile_repo.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    reference_connection_id = request.reference_connection_id or (
        str(profile.reference_connection_id) if profile.reference_connection_id else None
    )
    if not reference_connection_id:
        raise HTTPException(status_code=400, detail="Для профиля не задана эталонная БД")

    reference_connection = await connection_repo.get_connection_by_id(reference_connection_id)
    if not reference_connection:
        raise HTTPException(status_code=404, detail="Эталонное подключение не найдено")

    if str(reference_connection.schema_profile_id) != profile_id:
        await connection_repo.assign_profile(
            connection_id=reference_connection_id,
            schema_profile_id=profile_id,
            detected_profile_name=profile.name,
            profile_source='manual',
        )

    await profile_repo.update_profile(
        profile_id=profile_id,
        reference_connection_id=reference_connection_id,
    )

    generator = ScenarioGenerator(
        scenario_repository=None,
        connection_repo=connection_repo,
        bundle_repository=bundle_repo,
    )
    bundles = await generator.generate_bundles_for_profile(
        schema_profile_id=profile_id,
        reference_connection_id=reference_connection_id,
        scenario_types=request.scenario_template_ids,
    )

    refreshed_profile = await profile_repo.get_profile_by_id(profile_id)
    return SchemaProfileBundlesResponse(
        profile=SchemaProfileSummaryResponse(**refreshed_profile.to_dict()),
        bundles=bundles,
        generated_count=len(bundles),
    )
