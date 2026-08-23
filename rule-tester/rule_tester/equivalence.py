"""Exact output-equivalence checks."""

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
import math

from sqlglot import exp, parse_one

from .bootstrap import BACKEND_ROOT  # noqa: F401
from security import validate_read_only_query
from .models import EquivalenceEvidence
from .mysql_runtime import QueryExecutionFailure, execute_complete


def _normalize(value):
    if value is None:
        return ("null",)
    if isinstance(value, float) and math.isnan(value):
        return ("float", "nan")
    if isinstance(value, Decimal):
        return ("decimal", str(value))
    if isinstance(value, (datetime, date, time)):
        return (type(value).__name__, value.isoformat())
    if isinstance(value, bytes):
        return ("bytes", value.hex())
    if isinstance(value, (list, tuple)):
        return ("sequence", tuple(_normalize(item) for item in value))
    if isinstance(value, dict):
        return ("mapping", tuple(sorted((str(key), _normalize(item)) for key, item in value.items())))
    return (type(value).__name__, value)


def _normalized_rows(rows):
    return tuple(tuple(_normalize(value) for value in row) for row in rows)


def has_order_by(query: str) -> bool:
    statement = parse_one(query, read="mysql")
    return statement.find(exp.Order) is not None


def compare_queries(connection, original: str, candidate: str, *, max_rows: int) -> EquivalenceEvidence:
    try:
        original = validate_read_only_query(original)
        candidate = validate_read_only_query(candidate)
    except Exception:
        return EquivalenceEvidence(False, False, None, None, "VALIDATION_FAILED")

    ordered = has_order_by(original) or has_order_by(candidate)
    try:
        original_output = execute_complete(connection, original, max_rows=max_rows)
        candidate_output = execute_complete(connection, candidate, max_rows=max_rows)
    except QueryExecutionFailure as error:
        return EquivalenceEvidence(False, ordered, None, None, error.code)

    original_count = len(original_output.rows)
    candidate_count = len(candidate_output.rows)
    if original_output.truncated or candidate_output.truncated:
        return EquivalenceEvidence(False, ordered, original_count, candidate_count, "RESULT_TRUNCATED")
    if original_output.columns != candidate_output.columns:
        return EquivalenceEvidence(False, ordered, original_count, candidate_count, "COLUMN_MISMATCH")
    if original_count != candidate_count:
        return EquivalenceEvidence(False, ordered, original_count, candidate_count, "ROW_COUNT_MISMATCH")

    left = _normalized_rows(original_output.rows)
    right = _normalized_rows(candidate_output.rows)
    equal = left == right if ordered else Counter(left) == Counter(right)
    return EquivalenceEvidence(
        equal,
        ordered,
        original_count,
        candidate_count,
        "EQUIVALENT" if equal else "VALUE_OR_DUPLICATE_MISMATCH",
    )


def public_equivalence(evidence: EquivalenceEvidence) -> dict:
    return asdict(evidence)
