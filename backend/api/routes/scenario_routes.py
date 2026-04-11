"""
API роуты для управления сценариями тестирования
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from backend.api.schemas import GenerateScenariosRequest

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def get_scenario_repository():
    """Получить репозиторий сценариев"""
    from backend.initialize import SCENARIOS_ENABLED, scenario_repository
    if not SCENARIOS_ENABLED or not scenario_repository:
        raise HTTPException(status_code=503, detail="Сценарии тестирования не настроены")
    return scenario_repository


def get_connection_repository():
    """Получить репозиторий подключений."""
    from backend.initialize import connection_repository
    if not connection_repository:
        raise HTTPException(status_code=503, detail="Репозиторий подключений не настроен")
    return connection_repository


@router.get("")
async def get_scenarios(
    limit: int = 100,
    offset: int = 0,
    scenario_type: Optional[str] = None,
    include_builtin: bool = True,
    target_connection_id: Optional[str] = None,
    include_global: bool = True,
):
    """Получить список всех сценариев тестирования"""
    repo = get_scenario_repository()
    scenarios = await repo.get_all_scenarios(
        limit=limit,
        offset=offset,
        scenario_type=scenario_type,
        include_builtin=include_builtin,
        target_connection_id=target_connection_id,
        include_global=include_global,
    )
    return {"scenarios": scenarios, "total": len(scenarios)}


@router.post("/generate")
async def generate_scenarios(request: GenerateScenariosRequest):
    """Сгенерировать сценарии на основе схемы подключённой БД."""
    from backend.database.scenario_generator import ScenarioGenerator

    repo = get_scenario_repository()
    connection_repo = get_connection_repository()

    generator = ScenarioGenerator(
        scenario_repository=repo,
        connection_repo=connection_repo,
    )

    scenarios = await generator.generate_scenarios(
        connection_id=request.connection_id,
        scenario_types=request.scenario_types,
        replace_existing=request.replace_existing,
    )
    return {
        "scenarios": scenarios,
        "generated_count": len(scenarios),
    }


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """Получить сценарий по ID с запросами и параметрами"""
    repo = get_scenario_repository()
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")
    return scenario.to_dict()


@router.post("")
async def create_scenario(request):
    """Создать новый сценарий тестирования"""
    from backend.api.schemas import TestScenarioCreate
    request = TestScenarioCreate(**request)
    repo = get_scenario_repository()
    
    # Проверяем уникальность имени
    existing = await repo.get_scenario_by_name(request.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.name}' уже существует")

    # Создаём сценарий
    scenario = await repo.create_scenario(
        name=request.name,
        description=request.description,
        scenario_type=request.scenario_type,
        is_builtin=False,
        target_connection_id=request.target_connection_id,
    )

    # Добавляем запросы к сценарию
    for idx, query_data in enumerate(request.queries):
        query = await repo.add_query_to_scenario(
            scenario_id=str(scenario.id),
            sql_template=query_data.sql_template,
            query_type=query_data.query_type,
            weight=query_data.weight,
            order_index=query_data.order_index if query_data.order_index else idx,
            description=query_data.description
        )

        # Добавляем параметры к запросу
        for param_data in query_data.params:
            await repo.add_param_to_query(
                query_id=str(query.id),
                param_name=param_data.param_name,
                param_type=param_data.param_type,
                min_value=param_data.min_value,
                max_value=param_data.max_value,
                string_pattern=param_data.string_pattern,
                string_length=param_data.string_length,
                table_ref=param_data.table_ref,
                column_ref=param_data.column_ref,
                current_value=param_data.current_value,
                step=param_data.step
            )

    scenario_with_queries = await repo.get_scenario(str(scenario.id))
    return scenario_with_queries.to_dict()


@router.put("/{scenario_id}")
async def update_scenario(scenario_id: str, request):
    """Обновить сценарий тестирования"""
    from backend.api.schemas import TestScenarioUpdate
    request = TestScenarioUpdate(**request)
    repo = get_scenario_repository()
    
    # Проверяем существование
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    # Нельзя редактировать built-in сценарии (кроме is_active)
    if scenario.is_builtin == 't' and (request.name or request.description or request.scenario_type):
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    # Проверяем уникальность имени
    if request.name and request.name != scenario.name:
        existing = await repo.get_scenario_by_name(request.name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.name}' уже существует")

    updated = await repo.update_scenario(
        scenario_id=scenario_id,
        name=request.name,
        description=request.description,
        scenario_type=request.scenario_type,
        target_connection_id=request.target_connection_id,
        is_active=request.is_active
    )

    return updated.to_dict()


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """Удалить сценарий тестирования"""
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    deleted = await repo.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя удалить")

    return {"deleted": True, "scenario_id": scenario_id}


@router.post("/{scenario_id}/clone")
async def clone_scenario(scenario_id: str, request):
    """Клонировать сценарий тестирования"""
    from backend.api.schemas import CloneScenarioRequest
    request = CloneScenarioRequest(**request)
    repo = get_scenario_repository()
    
    # Проверяем существование оригинала
    original = await repo.get_scenario(scenario_id)
    if not original:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    # Проверяем уникальность нового имени
    existing = await repo.get_scenario_by_name(request.new_name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Сценарий с именем '{request.new_name}' уже существует")

    cloned = await repo.clone_scenario(scenario_id, request.new_name)
    return cloned.to_dict()


# ==================== Scenario Query Endpoints ====================

@router.get("/{scenario_id}/indexes")
async def get_scenario_indexes(scenario_id: str):
    """Получить все индексы сценария"""
    repo = get_scenario_repository()

    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    indexes = await repo.get_scenario_indexes(scenario_id)
    return {"indexes": [idx.to_dict() for idx in indexes]}


@router.post("/{scenario_id}/indexes")
async def add_index_to_scenario(scenario_id: str, request):
    """Добавить индекс к сценарию"""
    from backend.api.schemas import ScenarioIndexCreate
    request = ScenarioIndexCreate(**request)
    repo = get_scenario_repository()

    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    scenario_index = await repo.add_index_to_scenario(
        scenario_id=scenario_id,
        table_name=request.table_name,
        column_names=request.column_names,
        index_type=request.index_type,
        index_name=request.index_name,
        is_unique=request.is_unique,
        condition=request.condition,
        description=request.description,
    )
    return scenario_index.to_dict()


@router.put("/{scenario_id}/indexes/{index_id}")
async def update_scenario_index(scenario_id: str, index_id: str, request):
    """Обновить индекс сценария"""
    from backend.api.schemas import ScenarioIndexUpdate
    request = ScenarioIndexUpdate(**request)
    repo = get_scenario_repository()

    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    scenario_index = await repo.get_index(index_id)
    if not scenario_index or str(scenario_index.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Индекс {index_id} не найден в сценарии {scenario_id}")

    updated = await repo.update_index(
        index_id=index_id,
        table_name=request.table_name,
        column_names=request.column_names,
        index_type=request.index_type,
        index_name=request.index_name,
        is_unique=request.is_unique,
        condition=request.condition,
        description=request.description,
    )
    return updated.to_dict()


@router.delete("/{scenario_id}/indexes/{index_id}")
async def delete_scenario_index(scenario_id: str, index_id: str):
    """Удалить индекс сценария"""
    repo = get_scenario_repository()

    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    scenario_index = await repo.get_index(index_id)
    if not scenario_index or str(scenario_index.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Индекс {index_id} не найден в сценарии {scenario_id}")

    await repo.delete_index(index_id)
    return {"deleted": True, "index_id": index_id}


# ==================== Scenario Query Endpoints ====================

@router.get("/{scenario_id}/queries")
async def get_scenario_queries(scenario_id: str):
    """Получить все запросы сценария"""
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    queries = [q.to_dict() for q in scenario.queries]
    return {"queries": queries}


@router.post("/{scenario_id}/queries")
async def add_query_to_scenario(scenario_id: str, request):
    """Добавить запрос к сценарию"""
    from backend.api.schemas import ScenarioQueryCreate
    request = ScenarioQueryCreate(**request)
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.add_query_to_scenario(
        scenario_id=scenario_id,
        sql_template=request.sql_template,
        query_type=request.query_type,
        weight=request.weight,
        order_index=request.order_index,
        description=request.description
    )

    for param_data in request.params:
        await repo.add_param_to_query(
            query_id=str(query.id),
            param_name=param_data.param_name,
            param_type=param_data.param_type,
            min_value=param_data.min_value,
            max_value=param_data.max_value,
            string_pattern=param_data.string_pattern,
            string_length=param_data.string_length,
            table_ref=param_data.table_ref,
            column_ref=param_data.column_ref,
            current_value=param_data.current_value,
            step=param_data.step
        )

    query_result = await repo.get_query(str(query.id))
    return query_result.to_dict()


@router.put("/{scenario_id}/queries/{query_id}")
async def update_scenario_query(scenario_id: str, query_id: str, request):
    """Обновить запрос сценария"""
    from backend.api.schemas import ScenarioQueryUpdate
    request = ScenarioQueryUpdate(**request)
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    updated = await repo.update_query(
        query_id=query_id,
        sql_template=request.sql_template,
        query_type=request.query_type,
        weight=request.weight,
        order_index=request.order_index,
        description=request.description
    )

    return updated.to_dict()


@router.delete("/{scenario_id}/queries/{query_id}")
async def delete_scenario_query(scenario_id: str, query_id: str):
    """Удалить запрос из сценария"""
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    await repo.delete_query(query_id)
    return {"deleted": True, "query_id": query_id}


# ==================== Scenario Param Endpoints ====================

@router.get("/{scenario_id}/queries/{query_id}/params")
async def get_query_params(scenario_id: str, query_id: str):
    """Получить все параметры запроса"""
    repo = get_scenario_repository()
    
    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    params = [p.to_dict() for p in query.params]
    return {"params": params}


@router.post("/{scenario_id}/queries/{query_id}/params")
async def add_param_to_query(scenario_id: str, query_id: str, request):
    """Добавить параметр к запросу"""
    from backend.api.schemas import ScenarioParamCreate
    request = ScenarioParamCreate(**request)
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    param = await repo.add_param_to_query(
        query_id=query_id,
        param_name=request.param_name,
        param_type=request.param_type,
        min_value=request.min_value,
        max_value=request.max_value,
        string_pattern=request.string_pattern,
        string_length=request.string_length,
        table_ref=request.table_ref,
        column_ref=request.column_ref,
        current_value=request.current_value,
        step=request.step
    )

    return param.to_dict()


@router.put("/{scenario_id}/queries/{query_id}/params/{param_id}")
async def update_query_param(scenario_id: str, query_id: str, param_id: str, request):
    """Обновить параметр запроса"""
    from backend.api.schemas import ScenarioParamUpdate
    request = ScenarioParamUpdate(**request)
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    param = await repo.get_param(param_id)
    if not param or str(param.query_id) != query_id:
        raise HTTPException(status_code=404, detail=f"Параметр {param_id} не найден в запросе {query_id}")

    updated = await repo.update_param(
        param_id=param_id,
        param_name=request.param_name,
        param_type=request.param_type,
        min_value=request.min_value,
        max_value=request.max_value,
        string_pattern=request.string_pattern,
        string_length=request.string_length,
        table_ref=request.table_ref,
        column_ref=request.column_ref,
        current_value=request.current_value,
        step=request.step
    )

    return updated.to_dict()


@router.delete("/{scenario_id}/queries/{query_id}/params/{param_id}")
async def delete_query_param(scenario_id: str, query_id: str, param_id: str):
    """Удалить параметр запроса"""
    repo = get_scenario_repository()
    
    scenario = await repo.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Сценарий {scenario_id} не найден")

    if scenario.is_builtin == 't':
        raise HTTPException(status_code=403, detail="Встроенные сценарии нельзя редактировать")

    query = await repo.get_query(query_id)
    if not query or str(query.scenario_id) != scenario_id:
        raise HTTPException(status_code=404, detail=f"Запрос {query_id} не найден в сценарии {scenario_id}")

    param = await repo.get_param(param_id)
    if not param or str(param.query_id) != query_id:
        raise HTTPException(status_code=404, detail=f"Параметр {param_id} не найден в запросе {query_id}")

    await repo.delete_param(param_id)
    return {"deleted": True, "param_id": param_id}
