from optimizer import optimize_sql


def test_simple_select_star_expands_visible_schema_columns():
    result = optimize_sql("SELECT * FROM orders", lambda table: ["id", "created_at"] if table == "orders" else [])
    assert result.changed
    assert result.optimized_query == "SELECT `id`, `created_at` FROM orders"
    assert result.suggestions[0]["safety"] == "safe"


def test_join_select_star_is_not_silently_rewritten():
    query = "SELECT * FROM orders JOIN customers ON customers.id = orders.customer_id"
    result = optimize_sql(query, lambda _table: ["id"])
    assert result.optimized_query == query
    assert any(item["rule"] == "select-star" and not item["applied"] for item in result.suggestions)


def test_date_range_applies_only_to_verified_temporal_column():
    query = "SELECT id FROM orders WHERE YEAR(created_at) = 2025"
    unverified = optimize_sql(query)
    assert unverified.optimized_query == query
    verified = optimize_sql(query, resolve_column_type=lambda column: "datetime" if column == "created_at" else None)
    assert "created_at >= '2025-01-01'" in verified.optimized_query
    assert "created_at < '2026-01-01'" in verified.optimized_query


def test_year_month_uses_half_open_next_month_boundary():
    query = "SELECT id FROM orders WHERE YEAR(created_at)=2025 AND MONTH(created_at)=12"
    result = optimize_sql(query, resolve_column_type=lambda _column: "timestamp")
    assert "created_at >= '2025-12-01'" in result.optimized_query
    assert "created_at < '2026-01-01'" in result.optimized_query


def test_unsafe_rewrites_remain_suggestions():
    queries = [
        "SELECT id FROM users WHERE role='a' OR role='b'",
        "SELECT DISTINCT role, COUNT(*) FROM users GROUP BY role",
        "SELECT id FROM users WHERE team_id IN (SELECT id FROM teams)",
    ]
    for query in queries:
        result = optimize_sql(query)
        assert result.optimized_query == query
        assert any(not item["applied"] and item["safety"] in {"unsafe", "context-dependent"} for item in result.suggestions)

