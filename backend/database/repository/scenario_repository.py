"""
ScenarioRepository для работы со сценариями тестирования
"""
import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from backend.database.models import Base, TestScenario, ScenarioQuery, ScenarioParam, ScenarioIndex
from backend.database.repository.base import BaseRepository


class ScenarioRepository(BaseRepository):
    """Репозиторий для работы со сценариями тестирования"""

    async def init_db(self):
        """Создать все таблицы"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ==================== TestScenario CRUD ====================

    async def create_scenario(
        self,
        name: str,
        description: Optional[str],
        scenario_type: str,
        is_builtin: bool = False
    ) -> TestScenario:
        """Создать новый сценарий"""
        async with self.SessionLocal() as session:
            scenario = TestScenario(
                id=uuid.uuid4(),
                name=name,
                description=description,
                scenario_type=scenario_type,
                is_builtin='t' if is_builtin else 'f',
                is_active='t'
            )
            session.add(scenario)
            await session.commit()
            await session.refresh(scenario)
            return scenario

    async def get_scenario(self, scenario_id: str) -> Optional[TestScenario]:
        """Получить сценарий по ID с запросами и параметрами (eager loading)"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario)
                .options(
                    joinedload(TestScenario.queries).joinedload(ScenarioQuery.params),
                    joinedload(TestScenario.indexes),
                )
                .where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.unique().scalar_one_or_none()
            return scenario

    async def get_scenario_by_name(self, name: str) -> Optional[TestScenario]:
        """Получить сценарий по имени"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.name == name)
            )
            return result.scalar_one_or_none()

    async def get_all_scenarios(
        self,
        limit: int = 100,
        offset: int = 0,
        scenario_type: Optional[str] = None,
        include_builtin: bool = True
    ) -> List[Dict[str, Any]]:
        """Получить список всех сценариев"""
        async with self.SessionLocal() as session:
            query = select(TestScenario).options(
                joinedload(TestScenario.queries).joinedload(ScenarioQuery.params),
                joinedload(TestScenario.indexes),
            )

            if scenario_type:
                query = query.where(TestScenario.scenario_type == scenario_type)

            if not include_builtin:
                query = query.where(TestScenario.is_builtin == 'f')

            query = query.order_by(desc(TestScenario.created_at)).offset(offset).limit(limit)
            result = await session.execute(query)
            scenarios = result.unique().scalars().all()
            return [s.to_dict() for s in scenarios]

    async def update_scenario(
        self,
        scenario_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scenario_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[TestScenario]:
        """Обновить сценарий"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.scalar_one_or_none()

            if scenario:
                if name is not None:
                    scenario.name = name
                if description is not None:
                    scenario.description = description
                if scenario_type is not None:
                    scenario.scenario_type = scenario_type
                if is_active is not None:
                    scenario.is_active = 't' if is_active else 'f'

                await session.commit()
                await session.refresh(scenario)

            return scenario

    async def delete_scenario(self, scenario_id: str) -> bool:
        """Удалить сценарий (только если не built-in)"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario).where(TestScenario.id == uuid.UUID(scenario_id))
            )
            scenario = result.scalar_one_or_none()

            if scenario and scenario.is_builtin == 'f':
                await session.delete(scenario)
                await session.commit()
                return True
            return False

    async def clone_scenario(self, scenario_id: str, new_name: str) -> Optional[TestScenario]:
        """Клонировать сценарий"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario)
                .options(
                    joinedload(TestScenario.queries).joinedload(ScenarioQuery.params),
                    joinedload(TestScenario.indexes),
                )
                .where(TestScenario.id == uuid.UUID(scenario_id))
            )
            original = result.scalar_one_or_none()

            if not original:
                return None

            cloned = TestScenario(
                id=uuid.uuid4(),
                name=new_name,
                description=f"Копия: {original.description}" if original.description else None,
                scenario_type=original.scenario_type,
                is_builtin='f',
                is_active='t'
            )
            session.add(cloned)
            await session.flush()

            for orig_query in original.queries:
                new_query = ScenarioQuery(
                    id=uuid.uuid4(),
                    scenario_id=cloned.id,
                    sql_template=orig_query.sql_template,
                    query_type=orig_query.query_type,
                    weight=orig_query.weight,
                    order_index=orig_query.order_index,
                    description=orig_query.description
                )
                session.add(new_query)
                await session.flush()

                for orig_param in orig_query.params:
                    new_param = ScenarioParam(
                        id=uuid.uuid4(),
                        query_id=new_query.id,
                        param_name=orig_param.param_name,
                        param_type=orig_param.param_type,
                        min_value=orig_param.min_value,
                        max_value=orig_param.max_value,
                        string_pattern=orig_param.string_pattern,
                        string_length=orig_param.string_length,
                        table_ref=orig_param.table_ref,
                        column_ref=orig_param.column_ref,
                        current_value=orig_param.current_value,
                        step=orig_param.step
                    )
                    session.add(new_param)

            for orig_index in original.indexes:
                new_index = ScenarioIndex(
                    id=uuid.uuid4(),
                    scenario_id=cloned.id,
                    table_name=orig_index.table_name,
                    column_names=orig_index.column_names,
                    index_type=orig_index.index_type,
                    index_name=orig_index.index_name,
                    is_unique=orig_index.is_unique,
                    condition=orig_index.condition,
                    description=orig_index.description,
                )
                session.add(new_index)

            await session.commit()
            await session.refresh(cloned)
            return cloned

    # ==================== ScenarioQuery CRUD ====================

    async def add_query_to_scenario(
        self,
        scenario_id: str,
        sql_template: str,
        query_type: str,
        weight: int = 1,
        order_index: int = 0,
        description: Optional[str] = None
    ) -> ScenarioQuery:
        """Добавить запрос в сценарий"""
        async with self.SessionLocal() as session:
            query = ScenarioQuery(
                id=uuid.uuid4(),
                scenario_id=uuid.UUID(scenario_id),
                sql_template=sql_template,
                query_type=query_type,
                weight=weight,
                order_index=order_index,
                description=description
            )
            session.add(query)
            await session.commit()
            await session.refresh(query)
            return query

    async def get_query(self, query_id: str) -> Optional[ScenarioQuery]:
        """Получить запрос по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            return result.scalar_one_or_none()

    async def update_query(
        self,
        query_id: str,
        sql_template: Optional[str] = None,
        query_type: Optional[str] = None,
        weight: Optional[int] = None,
        order_index: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[ScenarioQuery]:
        """Обновить запрос"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            query = result.scalar_one_or_none()

            if query:
                if sql_template is not None:
                    query.sql_template = sql_template
                if query_type is not None:
                    query.query_type = query_type
                if weight is not None:
                    query.weight = weight
                if order_index is not None:
                    query.order_index = order_index
                if description is not None:
                    query.description = description

                await session.commit()
                await session.refresh(query)

            return query

    async def delete_query(self, query_id: str) -> bool:
        """Удалить запрос из сценария"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioQuery).where(ScenarioQuery.id == uuid.UUID(query_id))
            )
            query = result.scalar_one_or_none()

            if query:
                await session.delete(query)
                await session.commit()
                return True
            return False

    # ==================== ScenarioParam CRUD ====================

    async def add_param_to_query(
        self,
        query_id: str,
        param_name: str,
        param_type: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        string_pattern: Optional[str] = None,
        string_length: Optional[int] = None,
        table_ref: Optional[str] = None,
        column_ref: Optional[str] = None,
        current_value: int = 0,
        step: int = 1
    ) -> ScenarioParam:
        """Добавить параметр к запросу"""
        async with self.SessionLocal() as session:
            param = ScenarioParam(
                id=uuid.uuid4(),
                query_id=uuid.UUID(query_id),
                param_name=param_name,
                param_type=param_type,
                min_value=min_value,
                max_value=max_value,
                string_pattern=string_pattern,
                string_length=string_length,
                table_ref=table_ref,
                column_ref=column_ref,
                current_value=current_value,
                step=step
            )
            session.add(param)
            await session.commit()
            await session.refresh(param)
            return param

    async def get_param(self, param_id: str) -> Optional[ScenarioParam]:
        """Получить параметр по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            return result.scalar_one_or_none()

    async def update_param(
        self,
        param_id: str,
        param_name: Optional[str] = None,
        param_type: Optional[str] = None,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        string_pattern: Optional[str] = None,
        string_length: Optional[int] = None,
        table_ref: Optional[str] = None,
        column_ref: Optional[str] = None,
        current_value: Optional[int] = None,
        step: Optional[int] = None
    ) -> Optional[ScenarioParam]:
        """Обновить параметр"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param:
                if param_name is not None:
                    param.param_name = param_name
                if param_type is not None:
                    param.param_type = param_type
                if min_value is not None:
                    param.min_value = min_value
                if max_value is not None:
                    param.max_value = max_value
                if string_pattern is not None:
                    param.string_pattern = string_pattern
                if string_length is not None:
                    param.string_length = string_length
                if table_ref is not None:
                    param.table_ref = table_ref
                if column_ref is not None:
                    param.column_ref = column_ref
                if current_value is not None:
                    param.current_value = current_value
                if step is not None:
                    param.step = step

                await session.commit()
                await session.refresh(param)

            return param

    async def delete_param(self, param_id: str) -> bool:
        """Удалить параметр"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param:
                await session.delete(param)
                await session.commit()
                return True
            return False

    # ==================== ScenarioIndex CRUD ====================

    async def add_index_to_scenario(
        self,
        scenario_id: str,
        table_name: str,
        column_names: str,
        index_type: str = "btree",
        index_name: Optional[str] = None,
        is_unique: bool = False,
        condition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ScenarioIndex:
        """Добавить индекс к сценарию"""
        async with self.SessionLocal() as session:
            scenario_index = ScenarioIndex(
                id=uuid.uuid4(),
                scenario_id=uuid.UUID(scenario_id),
                table_name=table_name,
                column_names=column_names,
                index_type=index_type,
                index_name=index_name,
                is_unique='t' if is_unique else 'f',
                condition=condition,
                description=description,
            )
            session.add(scenario_index)
            await session.commit()
            await session.refresh(scenario_index)
            return scenario_index

    async def get_index(self, index_id: str) -> Optional[ScenarioIndex]:
        """Получить индекс сценария по ID"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioIndex).where(ScenarioIndex.id == uuid.UUID(index_id))
            )
            return result.scalar_one_or_none()

    async def get_scenario_indexes(self, scenario_id: str) -> List[ScenarioIndex]:
        """Получить все индексы сценария"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioIndex)
                .where(ScenarioIndex.scenario_id == uuid.UUID(scenario_id))
                .order_by(ScenarioIndex.table_name, ScenarioIndex.column_names)
            )
            return result.scalars().all()

    async def update_index(
        self,
        index_id: str,
        table_name: Optional[str] = None,
        column_names: Optional[str] = None,
        index_type: Optional[str] = None,
        index_name: Optional[str] = None,
        is_unique: Optional[bool] = None,
        condition: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[ScenarioIndex]:
        """Обновить индекс сценария"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioIndex).where(ScenarioIndex.id == uuid.UUID(index_id))
            )
            scenario_index = result.scalar_one_or_none()

            if scenario_index:
                if table_name is not None:
                    scenario_index.table_name = table_name
                if column_names is not None:
                    scenario_index.column_names = column_names
                if index_type is not None:
                    scenario_index.index_type = index_type
                if index_name is not None:
                    scenario_index.index_name = index_name
                if is_unique is not None:
                    scenario_index.is_unique = 't' if is_unique else 'f'
                if condition is not None:
                    scenario_index.condition = condition
                if description is not None:
                    scenario_index.description = description

                await session.commit()
                await session.refresh(scenario_index)

            return scenario_index

    async def delete_index(self, index_id: str) -> bool:
        """Удалить индекс сценария"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioIndex).where(ScenarioIndex.id == uuid.UUID(index_id))
            )
            scenario_index = result.scalar_one_or_none()

            if scenario_index:
                await session.delete(scenario_index)
                await session.commit()
                return True
            return False

    async def increment_sequential_param(self, param_id: str) -> int:
        """Инкрементировать значение sequential параметра"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(ScenarioParam).where(ScenarioParam.id == uuid.UUID(param_id))
            )
            param = result.scalar_one_or_none()

            if param and param.param_type == 'sequential_int':
                old_value = param.current_value
                param.current_value += param.step
                await session.commit()
                return old_value
            return 0

    # ==================== Helper Methods ====================

    async def get_scenario_for_execution(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Получить сценарий в формате для выполнения теста"""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(TestScenario)
                .options(
                    joinedload(TestScenario.queries).joinedload(ScenarioQuery.params),
                    joinedload(TestScenario.indexes),
                )
                .where(
                    TestScenario.id == uuid.UUID(scenario_id),
                    TestScenario.is_active == 't'
                )
            )
            scenario = result.unique().scalar_one_or_none()

            if not scenario:
                return None

            return {
                'id': str(scenario.id),
                'name': scenario.name,
                'scenario_type': scenario.scenario_type,
                'indexes': [
                    {
                        'id': str(idx.id),
                        'table_name': idx.table_name,
                        'column_names': idx.column_names,
                        'index_type': idx.index_type,
                        'index_name': idx.index_name,
                        'is_unique': idx.is_unique == 't',
                        'condition': idx.condition,
                        'description': idx.description,
                    }
                    for idx in scenario.indexes
                ],
                'queries': [
                    {
                        'id': str(q.id),
                        'sql_template': q.sql_template,
                        'query_type': q.query_type,
                        'weight': q.weight,
                        'params': [
                            {
                                'param_name': p.param_name,
                                'param_type': p.param_type,
                                'min_value': p.min_value,
                                'max_value': p.max_value,
                                'table_ref': p.table_ref,
                                'column_ref': p.column_ref,
                            }
                            for p in q.params
                        ]
                    }
                    for q in scenario.queries
                ]
            }
