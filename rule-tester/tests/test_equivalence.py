from rule_tester import equivalence
from rule_tester.models import QueryOutput
from rule_tester.mysql_runtime import QueryExecutionFailure


COLUMNS = (("value", 3),)


def test_unordered_equivalence_preserves_duplicates_and_nulls(monkeypatch):
    outputs = iter(
        [
            QueryOutput(COLUMNS, ((1,), (None,), (1,))),
            QueryOutput(COLUMNS, ((1,), (1,), (None,))),
        ]
    )
    monkeypatch.setattr(equivalence, "execute_complete", lambda *args, **kwargs: next(outputs))

    result = equivalence.compare_queries(object(), "SELECT 1", "SELECT 1", max_rows=10)

    assert result.equivalent
    assert result.reason_code == "EQUIVALENT"


def test_order_by_requires_identical_order(monkeypatch):
    outputs = iter(
        [
            QueryOutput(COLUMNS, ((1,), (2,))),
            QueryOutput(COLUMNS, ((2,), (1,))),
        ]
    )
    monkeypatch.setattr(equivalence, "execute_complete", lambda *args, **kwargs: next(outputs))

    result = equivalence.compare_queries(
        object(),
        "SELECT 1 AS value ORDER BY value",
        "SELECT 1 AS value ORDER BY value",
        max_rows=10,
    )

    assert not result.equivalent
    assert result.ordered
    assert result.reason_code == "VALUE_OR_DUPLICATE_MISMATCH"


def test_truncated_result_is_never_equivalent(monkeypatch):
    outputs = iter(
        [
            QueryOutput(COLUMNS, ((1,),), truncated=True),
            QueryOutput(COLUMNS, ((1,),)),
        ]
    )
    monkeypatch.setattr(equivalence, "execute_complete", lambda *args, **kwargs: next(outputs))

    result = equivalence.compare_queries(object(), "SELECT 1", "SELECT 1", max_rows=1)

    assert not result.equivalent
    assert result.reason_code == "RESULT_TRUNCATED"


def test_column_metadata_must_match(monkeypatch):
    outputs = iter(
        [
            QueryOutput((("left_name", 3),), ((1,),)),
            QueryOutput((("right_name", 3),), ((1,),)),
        ]
    )
    monkeypatch.setattr(equivalence, "execute_complete", lambda *args, **kwargs: next(outputs))

    result = equivalence.compare_queries(object(), "SELECT 1", "SELECT 1", max_rows=10)

    assert not result.equivalent
    assert result.reason_code == "COLUMN_MISMATCH"


def test_timeout_is_sanitized_and_rejected(monkeypatch):
    def fail(*args, **kwargs):
        raise QueryExecutionFailure("QUERY_TIMEOUT")

    monkeypatch.setattr(equivalence, "execute_complete", fail)
    result = equivalence.compare_queries(object(), "SELECT 1", "SELECT 1", max_rows=10)
    assert not result.equivalent
    assert result.reason_code == "QUERY_TIMEOUT"
