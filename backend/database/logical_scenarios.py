"""
Справочник логических сценариев нагрузки и built-in профилей схемы.
"""
from typing import Dict, List


LOGICAL_SCENARIO_TEMPLATES: List[Dict[str, str]] = [
    {
        "id": "read_only",
        "name": "Только чтение",
        "description": "Преимущественно точечные SELECT, JOIN и range scan без операций записи.",
    },
    {
        "id": "write_only",
        "name": "Только запись",
        "description": "Набор INSERT, UPDATE и DELETE операций без чтения.",
    },
    {
        "id": "mixed_light",
        "name": "Смешанная лёгкая",
        "description": "Смешанная нагрузка с преобладанием чтения и небольшим числом операций записи.",
    },
    {
        "id": "mixed_heavy",
        "name": "Смешанная тяжёлая",
        "description": "Более агрессивная смешанная нагрузка с заметной долей операций записи.",
    },
    {
        "id": "oltp",
        "name": "OLTP",
        "description": "Транзакционная нагрузка короткими операциями с чтением и записью.",
    },
    {
        "id": "olap",
        "name": "OLAP",
        "description": "Аналитическая нагрузка с агрегациями, JOIN и диапазонными чтениями.",
    },
]


BUILTIN_SCHEMA_PROFILES: List[Dict[str, str]] = [
    {
        "name": "sakila_like",
        "description": "Каталог фильмов и аренды: Sakila, Pagila и совместимые схемы.",
    },
    {
        "name": "olist_like",
        "description": "E-commerce и заказы маркетплейса: Olist и совместимые схемы.",
    },
]


LOGICAL_SCENARIO_TEMPLATE_IDS = [template["id"] for template in LOGICAL_SCENARIO_TEMPLATES]
