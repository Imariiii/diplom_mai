"""
Гибридное определение профиля модели данных по схеме БД.
"""
import re
from typing import Any, Dict, List, Optional

from backend.database.repository.profile_repository import ProfileRepository
from backend.database.schema_analyzer import SchemaAnalyzer, SchemaMetadata


SAKILA_MARKERS = {
    "actor",
    "film",
    "category",
    "customer",
    "inventory",
    "rental",
    "payment",
    "staff",
    "store",
    "language",
}

OLIST_MARKERS = {
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
    "customers",
    "products",
    "sellers",
    "geolocation",
    "product_category_name_translation",
}


class SchemaProfileResolver:
    """Определяет рекомендуемый schema_profile для подключения."""

    def __init__(self, connection_repo=None, profile_repository: Optional[ProfileRepository] = None):
        self.schema_analyzer = SchemaAnalyzer(connection_repo=connection_repo)
        self.profile_repository = profile_repository

    async def build_connection_profile_preview(self, connection_id: str) -> Dict[str, Any]:
        """Собрать preview схемы вместе с предложенным профилем."""
        metadata = await self.schema_analyzer.analyze_connection(connection_id)
        suggestion = await self.suggest_profile(metadata)
        preview = metadata.to_dict()
        preview["suggested_profile"] = suggestion
        return preview

    async def suggest_profile(self, metadata: SchemaMetadata) -> Dict[str, Any]:
        """Предложить профиль по сигнатуре таблиц."""
        detected = self._detect_profile(metadata)
        existing_profile = None
        if self.profile_repository:
            existing_profile = await self.profile_repository.get_profile_by_name(detected["name"])

        return {
            "name": detected["name"],
            "description": detected["description"],
            "confidence": detected["confidence"],
            "reason": detected["reason"],
            "existing_profile_id": str(existing_profile.id) if existing_profile else None,
            "is_existing": existing_profile is not None,
        }

    def _detect_profile(self, metadata: SchemaMetadata) -> Dict[str, Any]:
        table_names = {table_name.lower() for table_name in metadata.tables.keys()}

        sakila_hits = sorted(table_names.intersection(SAKILA_MARKERS))
        if len(sakila_hits) >= 3:
            return {
                "name": "sakila_like",
                "description": "Каталог фильмов и аренды: Sakila/Pagila-подобная модель.",
                "confidence": min(0.99, 0.45 + (len(sakila_hits) * 0.1)),
                "reason": f"Найдены характерные таблицы: {', '.join(sakila_hits[:5])}",
            }

        olist_hits = sorted(self._collect_olist_hits(table_names))
        if len(olist_hits) >= 3:
            return {
                "name": "olist_like",
                "description": "E-commerce / marketplace модель заказов в стиле Olist.",
                "confidence": min(0.99, 0.45 + (len(olist_hits) * 0.1)),
                "reason": f"Найдены характерные таблицы: {', '.join(olist_hits[:5])}",
            }

        generated_name = self._build_custom_profile_name(metadata.connection_name)
        return {
            "name": generated_name,
            "description": (
                f"Пользовательский профиль для схемы '{metadata.connection_name}'. "
                f"Автоопределение не смогло уверенно сопоставить её с built-in профилями."
            ),
            "confidence": 0.35,
            "reason": "Не найдено достаточного количества маркеров встроенных профилей.",
        }

    def _collect_olist_hits(self, table_names: set[str]) -> List[str]:
        hits = set(table_names.intersection(OLIST_MARKERS))
        for table_name in table_names:
            if table_name.startswith("olist_"):
                hits.add(table_name)
        return sorted(hits)

    def _build_custom_profile_name(self, connection_name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", connection_name.lower()).strip("_")
        if not base:
            base = "custom_schema"
        if not base.endswith("_like"):
            base = f"{base}_like"
        return base
