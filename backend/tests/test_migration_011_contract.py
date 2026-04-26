"""
Контрактные проверки миграции 011 logical database state.
"""
from pathlib import Path


def test_migration_011_backfills_existing_profiles_as_needs_review():
    """Старые logical DB с profile_id не должны получать ложный confirmed без strict validation."""
    migration = Path("backend/migrations/versions/011_add_logical_db_profile_state.py").read_text()

    assert "WHEN schema_profile_id IS NOT NULL THEN 'needs_review'" in migration
    assert "WHEN schema_profile_id IS NOT NULL THEN 'confirmed'" not in migration
