from rule_tester import candidates


def test_existing_select_star_rule_is_reused_without_modification(monkeypatch):
    monkeypatch.setattr(candidates, "table_columns", lambda connection, database, table: ["id", "name"])

    candidate = candidates.build_candidate(object(), "any_database", "select-star", "SELECT * FROM any_table")

    assert candidate.candidate_sql == "SELECT " + chr(96) + "id" + chr(96) + ", " + chr(96) + "name" + chr(96) + " FROM any_table"
    assert candidate.strict_machine_preconditions
    assert candidate.schema_agnostic_rule


def test_manual_candidate_cannot_assert_rule_level_preconditions():
    candidate = candidates.build_candidate(
        object(),
        "any_database",
        "manual",
        "SELECT 1",
        "SELECT 1",
    )

    assert not candidate.strict_machine_preconditions
    assert not candidate.schema_agnostic_rule
