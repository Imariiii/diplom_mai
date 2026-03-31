"""
Pydantic схемы для сценариев тестирования
"""
from pydantic import BaseModel
from typing import List, Optional


class ScenarioParamCreate(BaseModel):
    param_name: str
    param_type: str  # random_int, random_string, random_date, sequential_int, uuid, random_from_table
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    string_pattern: Optional[str] = None
    string_length: Optional[int] = None
    table_ref: Optional[str] = None
    column_ref: Optional[str] = None
    current_value: int = 0
    step: int = 1


class ScenarioParamUpdate(BaseModel):
    param_name: Optional[str] = None
    param_type: Optional[str] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    string_pattern: Optional[str] = None
    string_length: Optional[int] = None
    table_ref: Optional[str] = None
    column_ref: Optional[str] = None
    current_value: Optional[int] = None
    step: Optional[int] = None


class ScenarioParamResponse(BaseModel):
    id: str
    query_id: str
    param_name: str
    param_type: str
    min_value: Optional[int]
    max_value: Optional[int]
    string_pattern: Optional[str]
    string_length: Optional[int]
    table_ref: Optional[str]
    column_ref: Optional[str]
    current_value: Optional[int]
    step: Optional[int]
    created_at: str


class ScenarioQueryCreate(BaseModel):
    sql_template: str
    query_type: str  # select, insert, update, delete
    weight: int = 1
    order_index: int = 0
    description: Optional[str] = None
    params: List[ScenarioParamCreate] = []


class ScenarioQueryUpdate(BaseModel):
    sql_template: Optional[str] = None
    query_type: Optional[str] = None
    weight: Optional[int] = None
    order_index: Optional[int] = None
    description: Optional[str] = None


class ScenarioQueryResponse(BaseModel):
    id: str
    scenario_id: str
    sql_template: str
    query_type: str
    weight: int
    order_index: int
    description: Optional[str]
    created_at: str
    params: List[ScenarioParamResponse]


class TestScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scenario_type: str  # read_only, write_only, mixed_light, mixed_heavy, oltp, olap, custom
    queries: List[ScenarioQueryCreate] = []


class TestScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scenario_type: Optional[str] = None
    is_active: Optional[bool] = None


class TestScenarioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    scenario_type: str
    is_builtin: bool
    is_active: bool
    created_at: str
    updated_at: str
    queries: List[ScenarioQueryResponse]


class TestScenarioListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    scenario_type: str
    is_builtin: bool
    is_active: bool
    created_at: str


class CloneScenarioRequest(BaseModel):
    new_name: str