"""
Интеграционные тесты корректности backup/restore на реальных СУБД.
"""
import os
from decimal import Decimal
from typing import Dict

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.database.state_manager import DatabaseStateManager
from backend.database.sql_utils import register_engine_dbms_type


pytestmark = [pytest.mark.integration, pytest.mark.docker_integration]

DBMS_TYPES = ["postgresql", "mysql", "mariadb"]
TEST_PREFIXES = ("br_", "_loadtest_backup_")
DOCKER_ROOT_URLS = {
    "mysql": "mysql+aiomysql://root:root_pass@127.0.0.1:53306/restore_test",
    "mariadb": "mysql+aiomysql://root:root_pass@127.0.0.1:53307/restore_test",
}
ROOT_URL_ENVS = {
    "mysql": "BACKUP_RESTORE_MYSQL_ROOT_URL",
    "mariadb": "BACKUP_RESTORE_MARIADB_ROOT_URL",
}


async def _execute(engine: AsyncEngine, statements: list[str]) -> None:
    async with engine.connect() as conn:
        for statement in statements:
            await conn.execute(text(statement))
        await conn.commit()


async def _fetch_all(engine: AsyncEngine, sql: str):
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        return [tuple(row) for row in result.fetchall()]


async def _fetch_scalar(engine: AsyncEngine, sql: str):
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        return result.scalar()


async def _list_tables(engine: AsyncEngine, dbms_type: str) -> list[str]:
    if dbms_type == "postgresql":
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
    else:
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
    rows = await _fetch_all(engine, sql)
    return [row[0] for row in rows]


async def _ensure_disposable_database(engine: AsyncEngine, dbms_type: str) -> None:
    tables = await _list_tables(engine, dbms_type)
    foreign_tables = [
        table for table in tables
        if not table.startswith(TEST_PREFIXES)
    ]
    if foreign_tables and os.getenv("BACKUP_RESTORE_ALLOW_NONEMPTY") != "1":
        pytest.skip(
            f"База {dbms_type} не пустая: {foreign_tables}. "
            "Используйте отдельную тестовую БД или BACKUP_RESTORE_ALLOW_NONEMPTY=1."
        )


async def _drop_test_tables(engine: AsyncEngine, dbms_type: str) -> None:
    tables = [
        table for table in await _list_tables(engine, dbms_type)
        if table.startswith(TEST_PREFIXES)
    ]
    if not tables:
        return

    if dbms_type == "postgresql":
        quoted = ", ".join(f'"{table}"' for table in tables)
        await _execute(engine, [f"DROP TABLE IF EXISTS {quoted} CASCADE"])
        return

    statements = ["SET FOREIGN_KEY_CHECKS = 0"]
    statements.extend(f"DROP TABLE IF EXISTS `{table}`" for table in tables)
    statements.append("SET FOREIGN_KEY_CHECKS = 1")
    await _execute(engine, statements)


async def _setup_engine_for_schema(engine: AsyncEngine, dbms_type: str) -> AsyncEngine:
    """В Docker-режиме MySQL/MariaDB создаются root, чтобы trigger имел внешний DEFINER."""
    if os.getenv("BACKUP_RESTORE_USE_DOCKER") != "1" or dbms_type not in DOCKER_ROOT_URLS:
        return engine

    root_url = os.getenv(ROOT_URL_ENVS[dbms_type], DOCKER_ROOT_URLS[dbms_type])
    root_engine = create_async_engine(root_url, future=True)
    register_engine_dbms_type(root_engine, dbms_type)
    return root_engine


async def _setup_postgresql_schema(engine: AsyncEngine) -> None:
    await _execute(engine, [
        """
        CREATE TABLE br_item (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE br_child (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES br_item(id),
            note TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE br_audit (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES br_item(id),
            action TEXT NOT NULL
        )
        """,
        """
        CREATE OR REPLACE FUNCTION br_audit_item_insert()
        RETURNS trigger AS $$
        BEGIN
            INSERT INTO br_audit (item_id, action) VALUES (NEW.id, 'insert');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        CREATE TRIGGER br_item_insert
        AFTER INSERT ON br_item
        FOR EACH ROW EXECUTE FUNCTION br_audit_item_insert()
        """,
        """
        CREATE TABLE br_payment (
            id INTEGER NOT NULL,
            paid_on DATE NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            PRIMARY KEY (id, paid_on)
        ) PARTITION BY RANGE (paid_on)
        """,
        """
        CREATE TABLE br_payment_2024 PARTITION OF br_payment
        FOR VALUES FROM ('2024-01-01') TO ('2025-01-01')
        """,
        "INSERT INTO br_item (name) VALUES ('one'), ('two')",
        "INSERT INTO br_child (item_id, note) VALUES (1, 'child-one'), (2, 'child-two')",
        "INSERT INTO br_payment (id, paid_on, amount) VALUES (1, '2024-01-10', 10.00)",
    ])


async def _setup_mysql_family_schema(engine: AsyncEngine) -> None:
    await _execute(engine, [
        """
        CREATE TABLE br_item (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL
        )
        """,
        """
        CREATE TABLE br_child (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            item_id INTEGER NOT NULL,
            note VARCHAR(100) NOT NULL,
            CONSTRAINT fk_br_child_item FOREIGN KEY (item_id) REFERENCES br_item(id)
        )
        """,
        """
        CREATE TABLE br_audit (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            item_id INTEGER NOT NULL,
            action VARCHAR(100) NOT NULL,
            CONSTRAINT fk_br_audit_item FOREIGN KEY (item_id) REFERENCES br_item(id)
        )
        """,
        """
        CREATE TRIGGER br_item_insert
        AFTER INSERT ON br_item
        FOR EACH ROW
        BEGIN
            INSERT INTO br_audit (item_id, action) VALUES (NEW.id, 'insert');
        END
        """,
        """
        CREATE TABLE br_payment (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            paid_on DATE NOT NULL,
            amount DECIMAL(10, 2) NOT NULL
        )
        """,
        "INSERT INTO br_item (name) VALUES ('one'), ('two')",
        "INSERT INTO br_child (item_id, note) VALUES (1, 'child-one'), (2, 'child-two')",
        "INSERT INTO br_payment (paid_on, amount) VALUES ('2024-01-10', 10.00)",
    ])


async def setup_test_schema(engine: AsyncEngine, dbms_type: str) -> None:
    await _ensure_disposable_database(engine, dbms_type)
    await _drop_test_tables(engine, dbms_type)

    setup_engine = await _setup_engine_for_schema(engine, dbms_type)
    try:
        if dbms_type == "postgresql":
            await _setup_postgresql_schema(setup_engine)
        else:
            await _setup_mysql_family_schema(setup_engine)
    finally:
        if setup_engine is not engine:
            await setup_engine.dispose()


async def capture_state(engine: AsyncEngine, dbms_type: str) -> Dict[str, object]:
    payment_amount = await _fetch_scalar(
        engine,
        "SELECT amount FROM br_payment WHERE id = 1",
    )
    if isinstance(payment_amount, Decimal):
        payment_amount = str(payment_amount)

    return {
        "items": await _fetch_all(engine, "SELECT id, name FROM br_item ORDER BY id"),
        "children": await _fetch_all(engine, "SELECT id, item_id, note FROM br_child ORDER BY id"),
        "audit": await _fetch_all(engine, "SELECT id, item_id, action FROM br_audit ORDER BY id"),
        "payments": await _fetch_all(engine, "SELECT id, paid_on, amount FROM br_payment ORDER BY id"),
        "payment_amount": payment_amount,
        "item_count": await _fetch_scalar(engine, "SELECT COUNT(*) FROM br_item"),
        "child_count": await _fetch_scalar(engine, "SELECT COUNT(*) FROM br_child"),
    }


async def mutate_database(engine: AsyncEngine, dbms_type: str) -> None:
    await _execute(engine, [
        "UPDATE br_item SET name = 'changed' WHERE id = 1",
        "INSERT INTO br_item (name) VALUES ('transient')",
        "INSERT INTO br_child (item_id, note) VALUES (1, 'during-test')",
        "DELETE FROM br_child WHERE id = 1",
        "UPDATE br_payment SET amount = amount + 1 WHERE id = 1",
    ])


async def insert_after_restore(engine: AsyncEngine, dbms_type: str) -> int:
    async with engine.connect() as conn:
        await conn.execute(text("INSERT INTO br_item (name) VALUES ('after-restore')"))
        if dbms_type == "postgresql":
            result = await conn.execute(text("SELECT currval(pg_get_serial_sequence('br_item', 'id'))"))
        else:
            result = await conn.execute(text("SELECT LAST_INSERT_ID()"))
        await conn.commit()
        return int(result.scalar())


@pytest.mark.parametrize("db_engine", DBMS_TYPES, indirect=True)
async def test_native_readonly_queries_do_not_create_backup(
    db_engine: AsyncEngine,
    native_tools,
    request,
):
    dbms_type = request.node.callspec.params["db_engine"]
    native_tools(dbms_type)
    await setup_test_schema(db_engine, dbms_type)

    state_manager = DatabaseStateManager()

    assert not state_manager.needs_restore(["SELECT * FROM br_item WHERE id = 1"])


@pytest.mark.parametrize("db_engine", DBMS_TYPES, indirect=True)
async def test_native_backup_restore_contract(
    db_engine: AsyncEngine,
    native_strategy_context,
    native_tools,
    request,
):
    dbms_type = request.node.callspec.params["db_engine"]
    native_tools(dbms_type)

    await setup_test_schema(db_engine, dbms_type)
    before = await capture_state(db_engine, dbms_type)

    queries = [
        "UPDATE br_item SET name = 'changed' WHERE id = 1",
        "INSERT INTO br_child (item_id, note) VALUES (1, 'during-test')",
        "DELETE FROM br_child WHERE id = 1",
        "UPDATE br_payment SET amount = amount + 1 WHERE id = 1",
    ]

    with native_strategy_context():
        state_manager = DatabaseStateManager()
        prepare_result = await state_manager.prepare_for_test(db_engine, dbms_type, queries)

        assert prepare_result.needs_backup is True
        assert prepare_result.backup_info is not None
        if dbms_type == "mariadb" and os.getenv("BACKUP_RESTORE_USE_DOCKER") == "1":
            with open(prepare_result.backup_info.file_path, "rb") as dump_file:
                assert b"DEFINER" in dump_file.read()

        await mutate_database(db_engine, dbms_type)
        mutated = await capture_state(db_engine, dbms_type)
        assert mutated != before

        restore_result = await state_manager.restore_after_test(
            db_engine,
            dbms_type,
            prepare_result,
        )

    after = await capture_state(db_engine, dbms_type)
    next_id = await insert_after_restore(db_engine, dbms_type)
    audit_count_after_insert = await _fetch_scalar(
        db_engine,
        "SELECT COUNT(*) FROM br_audit",
    )

    assert restore_result.success is True
    assert restore_result.verified is True
    assert restore_result.errors == []
    assert after == before
    assert next_id == 3
    assert audit_count_after_insert == 3
