from index_advisor import suggest_indexes


class Cursor:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, sql, params):
        assert "INFORMATION_SCHEMA" in sql
        assert params == ("shop", "ratings")
        self.calls.append(sql)
    def fetchall(self):
        return next(self.responses)


class Connection:
    def __init__(self, indexes=()):
        self.cursor_instance = Cursor(iter([
            [("stars", "tinyint", None), ("rated_date", "date", None)],
            list(indexes),
        ]))
    def cursor(self): return self.cursor_instance


def test_missing_index_is_suggested_for_direct_filter_only():
    connection = Connection([("stars", "BTREE", None, "YES")])
    result = suggest_indexes(connection, "shop", "SELECT COUNT(*) FROM ratings WHERE rated_date = '2025-01-01'")
    assert len(result) == 1
    assert result[0]["column"] == "rated_date"
    assert result[0]["applied"] is False
    assert "write overhead" in result[0]["message"]


def test_visible_leading_composite_index_suppresses_duplicate_recommendation():
    connection = Connection([("rated_date", "BTREE", None, "YES")])
    assert suggest_indexes(connection, "shop", "SELECT * FROM ratings WHERE rated_date >= '2025-01-01'") == []


def test_nonleading_and_invisible_indexes_do_not_claim_full_leading_coverage():
    connection = Connection([("stars", "BTREE", None, "YES"), ("rated_date", "BTREE", None, "NO")])
    result = suggest_indexes(connection, "shop", "SELECT * FROM ratings WHERE stars = 5 AND rated_date < '2026-01-01'")
    assert [item["column"] for item in result] == ["rated_date"]


def test_prefix_index_does_not_count_as_full_column_index():
    connection = Connection([("rated_date", "BTREE", 4, "YES")])
    result = suggest_indexes(connection, "shop", "SELECT * FROM ratings WHERE rated_date = '2025-01-01'")
    assert [item["column"] for item in result] == ["rated_date"]
    assert "prefix index exists" in result[0]["message"]


def test_invisible_full_index_recommends_visibility_review():
    connection = Connection([("rated_date", "BTREE", None, "NO")])
    result = suggest_indexes(connection, "shop", "SELECT * FROM ratings WHERE rated_date = '2025-01-01'")
    assert "review its visibility" in result[0]["message"]


def test_any_visible_full_index_wins_over_other_prefix_indexes():
    connection = Connection([("rated_date", "BTREE", None, "YES"), ("rated_date", "BTREE", 4, "NO")])
    assert suggest_indexes(connection, "shop", "SELECT * FROM ratings WHERE rated_date = '2025-01-01'") == []


def test_ambiguous_or_computed_and_join_queries_are_skipped_without_metadata_lookup():
    queries = [
        "SELECT * FROM ratings WHERE stars = 5 OR rated_date = '2025-01-01'",
        "SELECT * FROM ratings WHERE DATE(rated_date) = '2025-01-01'",
        "SELECT * FROM ratings JOIN users ON ratings.user_id = users.id WHERE ratings.stars = 5",
        "SELECT * FROM ratings WHERE stars = (SELECT MAX(stars) FROM ratings)",
    ]
    for query in queries:
        connection = Connection()
        assert suggest_indexes(connection, "shop", query) == []
        assert connection.cursor_instance.calls == []
