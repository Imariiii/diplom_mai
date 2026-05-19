"""
API роуты для logical templates, schema profiles и bundle variants.
"""
from fastapi import APIRouter, HTTPException

from backend import initialize
from backend.api.schemas.connection_schemas import SchemaProfileSummaryResponse
from backend.api.schemas.profile_schemas import (
    ProfileBundleGenerateRequest,
    ScenarioBundleCloneRequest,
    ScenarioBundleSaveRequest,
    ScenarioBundleSummaryResponse,
    ScenarioTemplateCreateRequest,
    ScenarioTemplateListResponse,
    ScenarioTemplateResponse,
    ScenarioTemplateUpdateRequest,
    SchemaProfileBundlesResponse,
    SchemaProfileCreateRequest,
    SchemaProfileDetailResponse,
    SchemaProfileListResponse,
)
from backend.database.logical_scenarios import build_custom_template_id
from backend.database.scenario_generator import ScenarioGenerator

router = APIRouter(prefix="/api/schema-profiles", tags=["schema-profiles"])


def _validate_bundle_save_request(
    request: ScenarioBundleSaveRequest,
    *,
    is_create: bool = False,
) -> None:
    """Проверить согласованность workload_mode и содержимого bundle."""
    if request.workload_mode == "transaction":
        if not request.transactions:
            raise HTTPException(
                status_code=400,
                detail="Transaction bundle должен содержать хотя бы одну транзакцию",
            )
        for tx in request.transactions:
            if not is_create and not tx.steps:
                raise HTTPException(
                    status_code=400,
                    detail=f"Транзакция '{tx.name}' должна содержать хотя бы один шаг SQL",
                )
            for step in tx.steps:
                if not (step.sql_template or "").strip():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Транзакция '{tx.name}': шаг SQL не может быть пустым",
                    )
            param_names = [param.param_name for param in tx.params]
            if len(param_names) != len(set(param_names)):
                raise HTTPException(
                    status_code=400,
                    detail=f"Транзакция '{tx.name}': дублирующиеся param_name в параметрах",
                )
        return

    if not is_create and not request.queries:
        raise HTTPException(
            status_code=400,
            detail="Query bundle должен содержать хотя бы один SQL-запрос",
        )


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


async def _get_profile_or_404(profile_id: str):
    profile_repo = get_profile_repository()
    profile = await profile_repo.get_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    return profile


async def _get_bundle_or_404(profile_id: str, bundle_id: str):
    bundle_repo = get_bundle_repository()
    bundle = await bundle_repo.get_bundle(bundle_id)
    if not bundle or str(bundle.schema_profile_id) != profile_id:
        raise HTTPException(status_code=404, detail="Bundle не найден")
    return bundle


@router.get("/templates", response_model=ScenarioTemplateListResponse)
async def list_scenario_templates():
    """Получить список logical templates."""
    profile_repo = get_profile_repository()
    templates = await profile_repo.list_templates()
    return ScenarioTemplateListResponse(
        templates=[ScenarioTemplateResponse(**template.to_dict()) for template in templates]
    )


@router.post("/templates", response_model=ScenarioTemplateResponse, status_code=201)
async def create_scenario_template(request: ScenarioTemplateCreateRequest):
    """Создать пользовательский logical template."""
    profile_repo = get_profile_repository()
    existing_templates = await profile_repo.list_templates()
    template_id = build_custom_template_id(
        request.name,
        existing_ids=[template.id for template in existing_templates],
    )
    template = await profile_repo.create_template(
        template_id=template_id,
        name=request.name,
        description=request.description,
        is_builtin=False,
    )
    return ScenarioTemplateResponse(**template.to_dict())


@router.put("/templates/{template_id}", response_model=ScenarioTemplateResponse)
async def update_scenario_template(template_id: str, request: ScenarioTemplateUpdateRequest):
    """Обновить пользовательский logical template."""
    profile_repo = get_profile_repository()
    template = await profile_repo.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    if template.is_builtin == 't':
        raise HTTPException(status_code=400, detail="Нельзя изменять встроенный logical template")

    updated = await profile_repo.update_template(
        template_id=template_id,
        name=request.name,
        description=request.description,
    )
    return ScenarioTemplateResponse(**updated.to_dict())


@router.delete("/templates/{template_id}")
async def delete_scenario_template(template_id: str):
    """Удалить пользовательский logical template."""
    profile_repo = get_profile_repository()
    deleted = await profile_repo.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Шаблон не найден или является встроенным")
    return {"deleted": True, "template_id": template_id}


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
    """Получить профиль и все его bundle variants."""
    bundle_repo = get_bundle_repository()
    profile = await _get_profile_or_404(profile_id)
    bundles = await bundle_repo.list_bundles(schema_profile_id=profile_id)
    return SchemaProfileDetailResponse(
        **profile.to_dict(),
        bundles=[ScenarioBundleSummaryResponse(**bundle.to_dict()) for bundle in bundles],
    )


@router.post("/{profile_id}/bundles", response_model=ScenarioBundleSummaryResponse, status_code=201)
async def create_bundle_variant(profile_id: str, request: ScenarioBundleSaveRequest):
    """Создать bundle variant вручную."""
    profile_repo = get_profile_repository()
    bundle_repo = get_bundle_repository()
    await _get_profile_or_404(profile_id)
    template = await profile_repo.get_template(request.scenario_template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Logical template не найден")

    _validate_bundle_save_request(request, is_create=True)
    bundle = await bundle_repo.create_bundle_variant(
        schema_profile_id=profile_id,
        scenario_template_id=request.scenario_template_id,
        name=request.name,
        description=request.description,
        generation_source=request.generation_source,
        generated_from_connection_id=request.generated_from_connection_id,
        queries=[query.model_dump() for query in request.queries],
        indexes=[index.model_dump() for index in request.indexes],
        transactions=[tx.model_dump() for tx in request.transactions],
        workload_mode=request.workload_mode,
        is_active=request.is_active,
        is_builtin=False,
    )
    return ScenarioBundleSummaryResponse(**bundle.to_dict())


@router.get("/{profile_id}/bundles/{bundle_id}", response_model=ScenarioBundleSummaryResponse)
async def get_bundle_variant(profile_id: str, bundle_id: str):
    """Получить bundle variant."""
    bundle = await _get_bundle_or_404(profile_id, bundle_id)
    return ScenarioBundleSummaryResponse(**bundle.to_dict())


@router.put("/{profile_id}/bundles/{bundle_id}", response_model=ScenarioBundleSummaryResponse)
async def update_bundle_variant(profile_id: str, bundle_id: str, request: ScenarioBundleSaveRequest):
    """Полностью обновить bundle variant."""
    bundle = await _get_bundle_or_404(profile_id, bundle_id)
    if bundle.is_builtin == 't' and request.generation_source == "manual_variant":
        raise HTTPException(status_code=400, detail="Системный bundle нельзя переводить в manual variant")
    if request.scenario_template_id != bundle.scenario_template_id:
        raise HTTPException(status_code=400, detail="Нельзя менять logical template существующего bundle")

    bundle_repo = get_bundle_repository()
    try:
        _validate_bundle_save_request(request)
        updated = await bundle_repo.update_bundle_variant(
            bundle_id=bundle_id,
            name=request.name,
            description=request.description,
            generation_source=request.generation_source,
            generated_from_connection_id=request.generated_from_connection_id,
            queries=[query.model_dump() for query in request.queries],
            indexes=[index.model_dump() for index in request.indexes],
            transactions=[tx.model_dump() for tx in request.transactions],
            workload_mode=request.workload_mode,
            is_active=request.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ScenarioBundleSummaryResponse(**updated.to_dict())


@router.post("/{profile_id}/bundles/{bundle_id}/clone", response_model=ScenarioBundleSummaryResponse, status_code=201)
async def clone_bundle_variant(profile_id: str, bundle_id: str, request: ScenarioBundleCloneRequest):
    """Клонировать bundle variant в новый пользовательский variant."""
    await _get_bundle_or_404(profile_id, bundle_id)
    bundle_repo = get_bundle_repository()
    cloned = await bundle_repo.clone_bundle(bundle_id, request.name)
    if not cloned:
        raise HTTPException(status_code=404, detail="Bundle не найден")
    return ScenarioBundleSummaryResponse(**cloned.to_dict())


@router.post("/{profile_id}/bundles/{bundle_id}/activate", response_model=ScenarioBundleSummaryResponse)
async def activate_bundle_variant(profile_id: str, bundle_id: str):
    """Сделать bundle variant активным."""
    await _get_bundle_or_404(profile_id, bundle_id)
    bundle_repo = get_bundle_repository()
    activated = await bundle_repo.set_active_bundle(bundle_id)
    if not activated:
        raise HTTPException(status_code=404, detail="Bundle не найден")
    return ScenarioBundleSummaryResponse(**activated.to_dict())


@router.delete("/{profile_id}/bundles/{bundle_id}")
async def delete_bundle_variant(profile_id: str, bundle_id: str):
    """Удалить пользовательский неактивный variant."""
    await _get_bundle_or_404(profile_id, bundle_id)
    bundle_repo = get_bundle_repository()
    try:
        deleted = await bundle_repo.delete_bundle(bundle_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Bundle не найден")
    return {"deleted": True, "bundle_id": bundle_id}


@router.post("/{profile_id}/bundles/generate", response_model=SchemaProfileBundlesResponse)
async def generate_profile_bundles(profile_id: str, request: ProfileBundleGenerateRequest):
    """Сгенерировать или обновить системные canonical bundles профиля."""
    profile_repo = get_profile_repository()
    bundle_repo = get_bundle_repository()
    connection_repo = get_connection_repository()

    profile = await _get_profile_or_404(profile_id)
    logical_db_repo = getattr(initialize, "logical_database_repository", None)
    if logical_db_repo:
        logical_databases = await logical_db_repo.get_all_with_connections()
        logical_database = next(
            (
                item for item in logical_databases
                if (
                    item.schema_profile_id
                    and str(item.schema_profile_id) == profile_id
                    and item.profile_status == "confirmed"
                    and item.compatibility_status != "invalid"
                )
            ),
            None,
        )
        if logical_database:
            generator = ScenarioGenerator(
                connection_repo=connection_repo,
                bundle_repository=bundle_repo,
            )
            bundles = await generator.generate_bundles_for_logical_database(
                logical_database_id=str(logical_database.id),
                scenario_types=request.scenario_template_ids,
            )
            refreshed_profile = await profile_repo.get_profile_by_id(profile_id)
            return SchemaProfileBundlesResponse(
                profile=SchemaProfileSummaryResponse(**refreshed_profile.to_dict()),
                bundles=[ScenarioBundleSummaryResponse(**bundle) for bundle in bundles],
                generated_count=len(bundles),
            )

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
        bundles=[ScenarioBundleSummaryResponse(**bundle) for bundle in bundles],
        generated_count=len(bundles),
    )
