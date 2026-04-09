"""
Раннер последовательных миграций базы данных

Отслеживает применённые миграции через служебную таблицу _migrations.
Миграции из backend/migrations/versions/ сортируются по числовому префиксу
(001, 002, ...) и применяются в порядке возрастания.
"""
import importlib
import os
import pkgutil
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table,
    create_engine, inspect, text,
)


MIGRATIONS_TABLE = "_migrations"


def _ensure_migrations_table(engine) -> None:
    """Создать служебную таблицу _migrations, если её ещё нет."""
    meta = MetaData()
    if not inspect(engine).has_table(MIGRATIONS_TABLE):
        Table(
            MIGRATIONS_TABLE,
            meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String(255), nullable=False, unique=True),
            Column("applied_at", DateTime(timezone=True), nullable=False),
        )
        meta.create_all(engine)
        print(f"[MIGRATIONS] Создана служебная таблица {MIGRATIONS_TABLE}")


def _applied_migrations(engine) -> set:
    """Вернуть множество имён уже применённых миграций."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT name FROM {MIGRATIONS_TABLE} ORDER BY id")
        )
        return {row[0] for row in rows}


def _record_migration(conn, name: str) -> None:
    """Записать факт применения миграции."""
    conn.execute(
        text(
            f"INSERT INTO {MIGRATIONS_TABLE} (name, applied_at) VALUES (:name, :ts)"
        ),
        {"name": name, "ts": datetime.now(timezone.utc)},
    )


def _discover_migrations() -> list:
    """Найти все модули миграций в backend.migrations.versions и отсортировать."""
    versions_dir = os.path.join(os.path.dirname(__file__), "versions")
    migrations = []
    for importer, modname, ispkg in pkgutil.iter_modules([versions_dir]):
        if modname.startswith("_"):
            continue
        migrations.append(modname)
    migrations.sort()
    return migrations


def _sync_url(async_url: str) -> str:
    """Преобразовать asyncpg/async URL в синхронный psycopg2 URL."""
    url = async_url
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    url = url.replace("postgresql://", "postgresql+psycopg2://")
    if "psycopg2" not in url and url.startswith("postgresql"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def run_migrations(database_url: str) -> None:
    """Применить все неприменённые миграции к базе данных.

    Args:
        database_url: URL подключения (может быть asyncpg — будет сконвертирован).
    """
    sync_database_url = _sync_url(database_url)
    engine = create_engine(sync_database_url)

    try:
        _ensure_migrations_table(engine)
        applied = _applied_migrations(engine)
        available = _discover_migrations()

        pending = [m for m in available if m not in applied]

        if not pending:
            print("[MIGRATIONS] Все миграции уже применены")
            return

        print(f"[MIGRATIONS] Найдено {len(pending)} новых миграций")

        for migration_name in pending:
            print(f"[MIGRATIONS] ▶ Применяю {migration_name} ...")
            module = importlib.import_module(
                f"backend.migrations.versions.{migration_name}"
            )
            if not hasattr(module, "upgrade"):
                print(f"[MIGRATIONS] ⚠ {migration_name} не имеет функции upgrade(), пропуск")
                continue

            with engine.connect() as conn:
                with conn.begin():
                    module.upgrade(conn)
                    _record_migration(conn, migration_name)
            print(f"[MIGRATIONS] ✅ {migration_name} применена")

        print(f"[MIGRATIONS] Все миграции применены успешно")

    except Exception as e:
        print(f"[MIGRATIONS] ❌ Ошибка при выполнении миграций: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        engine.dispose()
