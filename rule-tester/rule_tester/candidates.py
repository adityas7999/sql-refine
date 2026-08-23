"""Adapters around existing optimizer rules; this module never edits rule state."""

from dataclasses import dataclass

from sqlglot import exp, parse_one

from .bootstrap import BACKEND_ROOT  # noqa: F401
from optimizer import OptimizationResult, _date_ranges, _select_star
from .mysql_runtime import column_type, table_columns


@dataclass(frozen=True)
class Candidate:
    rule_id: str
    classification: str
    original_sql: str
    candidate_sql: str
    strict_machine_preconditions: bool
    schema_agnostic_rule: bool


RULES = {
    "select-star": {
        "classification": "safe-with-schema-context",
        "description": "Expand a single-table SELECT * using visible columns.",
    },
    "date-range": {
        "classification": "safe-with-schema-context",
        "description": "Convert verified YEAR/MONTH temporal predicates to half-open ranges.",
    },
    "manual": {
        "classification": "unclassified-human-candidate",
        "description": "Compare pasted SQL without asserting rule-level safety.",
    },
}


class CandidateError(RuntimeError):
    pass


def _single_table(query: str) -> str:
    statement = parse_one(query, read="mysql")
    tables = list(statement.find_all(exp.Table))
    if len(tables) != 1 or not tables[0].name:
        raise CandidateError("The selected existing rule requires exactly one base table.")
    return tables[0].name


def build_candidate(connection, database: str, rule_id: str, original_sql: str, proposed_sql: str | None = None) -> Candidate:
    if rule_id not in RULES:
        raise CandidateError("Unknown rule.")
    if rule_id == "manual":
        if not proposed_sql or not proposed_sql.strip():
            raise CandidateError("Manual mode requires proposed SQL.")
        return Candidate(
            rule_id=rule_id,
            classification=RULES[rule_id]["classification"],
            original_sql=original_sql,
            candidate_sql=proposed_sql,
            strict_machine_preconditions=False,
            schema_agnostic_rule=False,
        )

    table = _single_table(original_sql)
    result = OptimizationResult(original_query=original_sql, optimized_query=original_sql.strip())
    if rule_id == "select-star":
        columns = table_columns(connection, database, table)
        _select_star(result, lambda requested: columns if requested == table else [])
    else:
        def resolve_type(reference: str) -> str | None:
            column = reference.rsplit(".", 1)[-1].strip(chr(96))
            return column_type(connection, database, table, column)

        _date_ranges(result, resolve_type)

    applied = any(item["rule"] == rule_id and item["applied"] for item in result.suggestions)
    if not applied or not result.changed:
        raise CandidateError("The existing rule did not produce an auto-applied candidate for this query.")
    return Candidate(
        rule_id=rule_id,
        classification=RULES[rule_id]["classification"],
        original_sql=original_sql,
        candidate_sql=result.optimized_query,
        strict_machine_preconditions=True,
        schema_agnostic_rule=True,
    )
