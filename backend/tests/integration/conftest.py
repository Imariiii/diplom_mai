"""
Фикстуры интеграционных тестов backup/restore.
"""
import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncIterator, Dict, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.core.config import settings
from backend.database.sql_utils import register_engine_dbms_type


COMPOSE_PROJECT = "backup_restore_tests"
COMPOSE_FILE = Path(__file__).with_name("docker-compose.backup-restore.yml")

DOCKER_URLS = {
    "postgresql": "postgresql+asyncpg://restore_user:restore_pass@127.0.0.1:55432/restore_test",
    "mysql": "mysql+aiomysql://restore_user:restore_pass@127.0.0.1:53306/restore_test",
    "mariadb": "mysql+aiomysql://restore_user:restore_pass@127.0.0.1:53307/restore_test",
}

ENV_URLS = {
    "postgresql": "BACKUP_RESTORE_POSTGRES_URL",
    "mysql": "BACKUP_RESTORE_MYSQL_URL",
    "mariadb": "BACKUP_RESTORE_MARIADB_URL",
}


def pytest_collection_modifyitems(config, items):
    """Не запускать integration-тесты без явного pytest -m integration."""
    markexpr = config.option.markexpr or ""
    if "integration" in markexpr or "docker_integration" in markexpr:
        return

    skip_integration = pytest.mark.skip(
        reason="Integration tests запускаются явно: pytest -m integration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def _docker_compose_cmd() -> list[str]:
    return ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE)]


@pytest.fixture(scope="session")
def docker_services() -> Iterator[None]:
    """Поднять test-only PostgreSQL/MySQL/MariaDB, если выбран Docker-режим."""
    if os.getenv("BACKUP_RESTORE_NATIVE_RUNNER") == "1":
        yield
        return

    if os.getenv("BACKUP_RESTORE_USE_DOCKER") != "1":
        yield
        return

    if not shutil.which("docker"):
        pytest.skip("Docker CLI не найден")

    cmd = _docker_compose_cmd()
    try:
        subprocess.run(cmd + ["up", "-d", "--wait"], check=True)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Не удалось поднять test DB через Docker Compose: {exc}")

    try:
        yield
    finally:
        subprocess.run(cmd + ["down", "-v"], check=False)


async def _wait_for_engine(engine: AsyncEngine, attempts: int = 30) -> None:
    last_error = None
    for _ in range(attempts):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)

    raise RuntimeError(f"СУБД не готова к тестам: {last_error}")


def _engine_url_for(dbms_type: str) -> str:
    env_name = ENV_URLS[dbms_type]
    url = os.getenv(env_name)
    if url:
        return url

    if os.getenv("BACKUP_RESTORE_USE_DOCKER") == "1":
        return DOCKER_URLS[dbms_type]

    pytest.skip(f"Не задан {env_name}; integration тест для {dbms_type} пропущен")


@pytest_asyncio.fixture
async def db_engine(request, docker_services) -> AsyncIterator[AsyncEngine]:
    """Создать AsyncEngine для параметризованного типа СУБД."""
    dbms_type = request.param
    engine = create_async_engine(_engine_url_for(dbms_type), future=True)
    register_engine_dbms_type(engine, dbms_type)

    await _wait_for_engine(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@contextmanager
def native_restore_strategy() -> Iterator[None]:
    """Временно включить native strategy для integration-теста."""
    previous_strategy = settings.restore.default_strategy
    previous_verify = settings.restore.verify_after_restore
    previous_checksums = settings.restore.verify_checksums
    previous_checksum_max_rows = settings.restore.checksum_max_rows
    previous_snapshots_dir = settings.paths.snapshots_dir

    snapshots_dir = Path(".pytest_cache") / "backup_restore_snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    settings.restore.default_strategy = "native"
    settings.restore.verify_after_restore = True
    settings.restore.verify_checksums = True
    settings.restore.checksum_max_rows = 10_000
    settings.paths.snapshots_dir = str(snapshots_dir)
    try:
        yield
    finally:
        settings.restore.default_strategy = previous_strategy
        settings.restore.verify_after_restore = previous_verify
        settings.restore.verify_checksums = previous_checksums
        settings.restore.checksum_max_rows = previous_checksum_max_rows
        settings.paths.snapshots_dir = previous_snapshots_dir


@pytest.fixture
def native_strategy_context():
    """Вернуть context manager для временного включения native strategy."""
    return native_restore_strategy


def _command_available(command: str) -> bool:
    try:
        return subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0
    except FileNotFoundError:
        return False


@asynccontextmanager
async def db_connection(engine: AsyncEngine):
    """Открыть соединение и гарантированно закрыть его после операций."""
    async with engine.connect() as conn:
        yield conn


def require_native_tools(dbms_type: str) -> None:
    """Проверить CLI-клиенты native dump/restore для конкретной СУБД."""
    missing_reason = None
    if dbms_type == "postgresql":
        if not _command_available("pg_dump") or not _command_available("pg_restore"):
            missing_reason = "pg_dump/pg_restore не найдены или неработоспособны"
    elif dbms_type == "mysql":
        if not (_command_available("mysqldump") or _command_available("mariadb-dump")):
            missing_reason = "mysqldump/mariadb-dump не найдены или неработоспособны"
        elif not (_command_available("mysql") or _command_available("mariadb")):
            missing_reason = "mysql/mariadb client не найден или неработоспособен"
    elif dbms_type == "mariadb":
        if not (_command_available("mariadb-dump") or _command_available("mysqldump")):
            missing_reason = "mariadb-dump/mysqldump не найдены или неработоспособны"
        elif not (_command_available("mariadb") or _command_available("mysql")):
            missing_reason = "mariadb/mysql client не найден или неработоспособен"

    if not missing_reason:
        return

    if os.getenv("BACKUP_RESTORE_NATIVE_RUNNER") == "1":
        pytest.fail(missing_reason)
    pytest.skip(missing_reason)


@pytest.fixture
def native_tools():
    """Вернуть функцию строгой проверки native CLI-клиентов."""
    return require_native_tools


async def fetch_scalar(engine: AsyncEngine, sql: str):
    async with db_connection(engine) as conn:
        result = await conn.execute(text(sql))
        return result.scalar()


async def fetch_all(engine: AsyncEngine, sql: str):
    async with db_connection(engine) as conn:
        result = await conn.execute(text(sql))
        return result.fetchall()


async def execute_statements(engine: AsyncEngine, statements: list[str]) -> None:
    async with db_connection(engine) as conn:
        for statement in statements:
            await conn.execute(text(statement))
        await conn.commit()
