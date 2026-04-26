"""
Unit-тесты для backend/database/backup_strategies/native_strategy.py.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.database.backup_strategies.native_strategy import NativeDumpStrategy


class _FakeProcess:
    """Минимальная имитация subprocess для async restore-тестов."""

    def __init__(self, returncode=0, stderr=b""):
        self.returncode = returncode
        self._stderr = stderr

    async def communicate(self, input=None):
        return b"", self._stderr


def test_sanitize_mysql_dump_definers_removes_versioned_trigger_definer():
    sql = b"""
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `ins_film` AFTER INSERT ON `film` FOR EACH ROW BEGIN
    INSERT INTO film_text (film_id, title) VALUES (new.film_id, new.title);
END */
"""

    sanitized, removed_count = NativeDumpStrategy._sanitize_mysql_dump_definers(sql)

    assert removed_count == 1
    assert b"DEFINER" not in sanitized
    assert b"CREATE*/ /*!50003 TRIGGER `ins_film`" in sanitized


def test_sanitize_mysql_dump_definers_removes_plain_routine_definer():
    sql = b"CREATE DEFINER=`app`@`%` PROCEDURE `rebuild_stats`() BEGIN SELECT 1; END"

    sanitized, removed_count = NativeDumpStrategy._sanitize_mysql_dump_definers(sql)

    assert removed_count == 1
    assert sanitized == b"CREATE PROCEDURE `rebuild_stats`() BEGIN SELECT 1; END"


def test_sanitize_mysql_dump_definers_keeps_sql_without_definer():
    sql = b"CREATE TRIGGER `ins_film` AFTER INSERT ON `film` FOR EACH ROW SET @x = 1;"

    sanitized, removed_count = NativeDumpStrategy._sanitize_mysql_dump_definers(sql)

    assert removed_count == 0
    assert sanitized == sql


@pytest.mark.asyncio
async def test_create_postgres_backup_uses_custom_format_and_selected_tables(monkeypatch):
    strategy = NativeDumpStrategy()
    captured_cmd = []

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmd.extend(cmd)
        return _FakeProcess(returncode=0)

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )

    file_path = await strategy._create_postgres_backup(
        "abc123",
        {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "restore_test",
        },
        {"br_item", "br_child"},
    )

    assert file_path.endswith("abc123.dump")
    assert "pg_dump" in captured_cmd
    assert "--format=custom" in captured_cmd
    assert "--no-owner" in captured_cmd
    assert "--no-privileges" in captured_cmd
    assert captured_cmd.count("-t") == 2
    assert "br_item" in captured_cmd
    assert "br_child" in captured_cmd


@pytest.mark.asyncio
async def test_create_mysql_backup_uses_native_dump_options(monkeypatch):
    strategy = NativeDumpStrategy()
    captured_cmd = []

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmd.extend(cmd)
        return _FakeProcess(returncode=0)

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )
    monkeypatch.setattr(
        NativeDumpStrategy,
        "_resolve_mysql_binaries",
        staticmethod(lambda dbms_type: ("/usr/bin/mariadb-dump", "/usr/bin/mariadb")),
    )

    file_path = await strategy._create_mysql_backup(
        "abc123",
        {
            "host": "localhost",
            "port": 3306,
            "user": "restore_user",
            "password": "restore_pass",
            "database": "restore_test",
        },
        {"br_item", "br_child"},
        "mariadb",
    )

    assert file_path.endswith("abc123.sql")
    assert captured_cmd[0] == "/usr/bin/mariadb-dump"
    assert "--single-transaction" in captured_cmd
    assert "--triggers" in captured_cmd
    assert "--hex-blob" in captured_cmd
    assert "--no-tablespaces" in captured_cmd
    assert "--skip-ssl" in captured_cmd
    assert "restore_test" in captured_cmd
    assert "br_item" in captured_cmd
    assert "br_child" in captured_cmd


@pytest.mark.asyncio
async def test_truncate_postgres_tables_uses_single_cascade_statement():
    strategy = NativeDumpStrategy()
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.commit = AsyncMock()

    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=conn)
    context.__aexit__ = AsyncMock(return_value=None)

    engine = MagicMock()
    engine.connect.return_value = context

    await strategy._truncate_postgres_tables(engine, {"rental", "film"})

    statement = conn.execute.await_args.args[0]
    assert str(statement) == (
        'TRUNCATE TABLE "film", "rental" RESTART IDENTITY CASCADE'
    )
    conn.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_postgres_backup_uses_data_only_pg_restore(monkeypatch):
    strategy = NativeDumpStrategy()
    strategy._truncate_postgres_tables = AsyncMock()
    captured_cmd = []

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmd.extend(cmd)
        return _FakeProcess(returncode=0)

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )

    await strategy._restore_postgres_backup(
        engine=MagicMock(),
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "restore_test",
        },
        file_path="/tmp/backup.dump",
        tables={"br_item"},
    )

    assert "--data-only" in captured_cmd
    assert "--disable-triggers" in captured_cmd
    assert "--clean" not in captured_cmd
    assert "--if-exists" not in captured_cmd
    strategy._truncate_postgres_tables.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_postgres_backup_fails_on_nonzero_pg_restore(monkeypatch):
    strategy = NativeDumpStrategy()
    strategy._truncate_postgres_tables = AsyncMock()

    async def fake_subprocess_exec(*cmd, **kwargs):
        return _FakeProcess(returncode=1, stderr=b"pg_restore failed")

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )

    with pytest.raises(RuntimeError, match="pg_restore failed"):
        await strategy._restore_postgres_backup(
            engine=MagicMock(),
            conn_params={
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "",
                "database": "restore_test",
            },
            file_path="/tmp/backup.dump",
            tables={"br_item"},
        )


@pytest.mark.asyncio
async def test_restore_mysql_backup_sanitizes_definers_before_import(monkeypatch, tmp_path):
    strategy = NativeDumpStrategy()
    dump_file = tmp_path / "backup.sql"
    dump_file.write_bytes(
        b"/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ "
        b"/*!50003 TRIGGER `br_item_insert` AFTER INSERT ON `br_item` "
        b"FOR EACH ROW SET @x = 1 */"
    )
    captured_input = {}

    class _CapturingProcess(_FakeProcess):
        async def communicate(self, input=None):
            captured_input["sql"] = input
            return b"", b""

    async def fake_subprocess_exec(*cmd, **kwargs):
        return _CapturingProcess(returncode=0)

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )
    monkeypatch.setattr(
        NativeDumpStrategy,
        "_resolve_mysql_binaries",
        staticmethod(lambda dbms_type: ("/usr/bin/mariadb-dump", "/usr/bin/mariadb")),
    )

    await strategy._restore_mysql_backup(
        {
            "host": "localhost",
            "port": 3306,
            "user": "restore_user",
            "password": "restore_pass",
            "database": "restore_test",
        },
        str(dump_file),
        "mariadb",
    )

    assert b"DEFINER" not in captured_input["sql"]
    assert b"TRIGGER `br_item_insert`" in captured_input["sql"]


@pytest.mark.asyncio
async def test_restore_mysql_backup_fails_on_nonzero_client(monkeypatch, tmp_path):
    strategy = NativeDumpStrategy()
    dump_file = tmp_path / "backup.sql"
    dump_file.write_bytes(b"SELECT 1;")

    async def fake_subprocess_exec(*cmd, **kwargs):
        return _FakeProcess(returncode=1, stderr=b"restore failed")

    monkeypatch.setattr(
        "backend.database.backup_strategies.native_strategy.asyncio.create_subprocess_exec",
        fake_subprocess_exec,
    )
    monkeypatch.setattr(
        NativeDumpStrategy,
        "_resolve_mysql_binaries",
        staticmethod(lambda dbms_type: ("/usr/bin/mariadb-dump", "/usr/bin/mariadb")),
    )

    with pytest.raises(RuntimeError, match="restore failed"):
        await strategy._restore_mysql_backup(
            {
                "host": "localhost",
                "port": 3306,
                "user": "restore_user",
                "password": "",
                "database": "restore_test",
            },
            str(dump_file),
            "mariadb",
        )
