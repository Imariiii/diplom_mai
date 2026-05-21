"""
Справочник логических сценариев нагрузки и built-in профилей схемы.
"""
import re
import uuid
from typing import Dict, Iterable, List


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
        "name": "Аналитические запросы",
        "description": "Аналитические запросы с агрегациями, JOIN и диапазонными чтениями.",
    },
]


LOGICAL_SCENARIO_TEMPLATE_IDS = [template["id"] for template in LOGICAL_SCENARIO_TEMPLATES]
BUILTIN_LOGICAL_SCENARIO_TEMPLATE_IDS = set(LOGICAL_SCENARIO_TEMPLATE_IDS)

# Шаблоны, для которых bootstrap/provisioner создают query-bundle автоматически.
# OLTP исключён: transaction-bundle задаётся вручную (см. oltp_transaction_seeds.py).
AUTO_GENERATED_SCENARIO_TEMPLATE_IDS = [
    template_id for template_id in LOGICAL_SCENARIO_TEMPLATE_IDS if template_id != "oltp"
]
MANUAL_OLTP_TEMPLATE_ID = "oltp"
MANUAL_OLTP_GENERATION_SOURCE = "manual_oltp_transactions_v2"


def build_custom_template_id(name: str, existing_ids: Iterable[str] = ()) -> str:
    """Построить machine id для пользовательского logical template."""
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    base_id = f"custom_{normalized}" if normalized else f"custom_{uuid.uuid4().hex[:8]}"
    candidate = base_id
    suffix = 2
    existing = set(existing_ids)
    while candidate in existing or candidate in BUILTIN_LOGICAL_SCENARIO_TEMPLATE_IDS:
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    return candidate
