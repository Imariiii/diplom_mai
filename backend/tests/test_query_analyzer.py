"""
Unit-тесты для backend/database/query_analyzer.py
Проверка классификации SQL-запросов, извлечения таблиц,
нормализации и полного анализа сценариев.
"""
import pytest

from backend.database.query_analyzer import QueryAnalyzer


@pytest.fixture
def analyzer():
    return QueryAnalyzer()


# =========================================================================
# has_write_operations
# =========================================================================

class TestHasWriteOperations:
    @pytest.mark.parametrize("query,expected", [
        ("SELECT * FROM film", False),
        ("SELECT COUNT(*) FROM actor WHERE actor_id > 5", False),
        ("UPDATE film SET title = 'X' WHERE film_id = 1", True),
        ("INSERT INTO actor (first_name) VALUES ('Test')", True),
        ("DELETE FROM rental WHERE rental_id = 999", True),
        ("TRUNCATE TABLE payment", True),
        ("REPLACE INTO config (key, value) VALUES ('a', 'b')", True),
        ("MERGE INTO target USING source ON target.id = source.id", True),
    ])
    def test_single_query(self, analyzer, query, expected):
        assert analyzer.has_write_operations([query]) is expected

    def test_mixed_queries(self, analyzer):
        queries = [
            "SELECT * FROM film",
            "UPDATE film SET title = 'X' WHERE film_id = 1",
        ]
        assert analyzer.has_write_operations(queries) is True

    def test_all_reads(self, analyzer):
        queries = [
            "SELECT * FROM film",
            "SELECT * FROM actor",
            "SELECT COUNT(*) FROM rental",
        ]
        assert analyzer.has_write_operations(queries) is False

    def test_empty_list(self, analyzer):
        assert analyzer.has_write_operations([]) is False


# =========================================================================
# extract_affected_tables
# =========================================================================

class TestExtractAffectedTables:
    def test_update(self, analyzer):
        tables = analyzer.extract_affected_tables(["UPDATE film SET title = 'X'"])
        assert "film" in tables

    def test_insert(self, analyzer):
        tables = analyzer.extract_affected_tables([
            "INSERT INTO actor (first_name) VALUES ('Test')"
        ])
        assert "actor" in tables

    def test_delete(self, analyzer):
        tables = analyzer.extract_affected_tables([
            "DELETE FROM rental WHERE rental_id = 1"
        ])
        assert "rental" in tables

    def test_select_not_included(self, analyzer):
        tables = analyzer.extract_affected_tables([
            "SELECT * FROM film",
            "UPDATE actor SET first_name = 'X'",
        ])
        assert "film" not in tables
        assert "actor" in tables

    def test_backtick_table_names(self, analyzer):
        tables = analyzer.extract_affected_tables([
            "UPDATE `film` SET title = 'X'"
        ])
        assert "film" in tables

    def test_multiple_tables(self, analyzer):
        tables = analyzer.extract_affected_tables([
            "UPDATE film SET title = 'A'",
            "DELETE FROM actor WHERE actor_id = 1",
            "INSERT INTO payment (amount) VALUES (10)",
        ])
        assert tables == {"film", "actor", "payment"}


# =========================================================================
# classify_queries
# =========================================================================

class TestClassifyQueries:
    def test_mixed_operations(self, analyzer):
        queries = [
            "SELECT * FROM film",
            "UPDATE film SET title = 'A'",
            "DELETE FROM actor WHERE actor_id = 1",
            "INSERT INTO payment (amount) VALUES (10)",
        ]
        classification = analyzer.classify_queries(queries)
        assert "UPDATE" in classification.get("film", set())
        assert "DELETE" in classification.get("actor", set())
        assert "INSERT" in classification.get("payment", set())

    def test_select_not_classified(self, analyzer):
        classification = analyzer.classify_queries(["SELECT * FROM film"])
        assert len(classification) == 0


# =========================================================================
# _normalize_query
# =========================================================================

class TestNormalizeQuery:
    def test_removes_single_line_comments(self, analyzer):
        result = analyzer._normalize_query("SELECT * FROM film -- this is a comment")
        assert "--" not in result

    def test_removes_multi_line_comments(self, analyzer):
        result = analyzer._normalize_query("SELECT /* comment */ * FROM film")
        assert "comment" not in result

    def test_collapses_whitespace(self, analyzer):
        result = analyzer._normalize_query("SELECT  *   FROM    film")
        assert "  " not in result

    def test_preserves_named_parameters(self, analyzer):
        result = analyzer._normalize_query("SELECT * FROM film WHERE film_id = :film_id")
        assert ":film_id" in result


# =========================================================================
# analyze_scenario
# =========================================================================

class TestAnalyzeScenario:
    def test_full_analysis(self, analyzer):
        queries = [
            "SELECT * FROM film WHERE film_id = :id",
            "UPDATE film SET title = :title WHERE film_id = :id",
            "INSERT INTO rental (customer_id) VALUES (:cid)",
            "SELECT COUNT(*) FROM actor",
        ]
        analysis = analyzer.analyze_scenario(queries)

        assert analysis["has_write_operations"] is True
        assert analysis["total_queries"] == 4
        assert analysis["write_queries"] == 2
        assert "film" in analysis["affected_tables"]
        assert "rental" in analysis["affected_tables"]

    def test_read_only_scenario(self, analyzer):
        queries = [
            "SELECT * FROM film",
            "SELECT * FROM actor",
        ]
        analysis = analyzer.analyze_scenario(queries)

        assert analysis["has_write_operations"] is False
        assert analysis["write_queries"] == 0
        assert analysis["affected_tables"] == []

    def test_empty_scenario(self, analyzer):
        analysis = analyzer.analyze_scenario([])
        assert analysis["total_queries"] == 0
        assert analysis["write_queries"] == 0
