"""
Unit-тесты для backend/database/backup_strategies/native_strategy.py.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.database.backup_strategies.native_strategy import NativeDumpStrategy


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
