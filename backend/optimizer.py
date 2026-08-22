"""Understandable, conservative SQL optimization rules.

Regex is intentionally limited to simple MySQL SELECT statements. Rules that cannot
be proven semantics-preserving produce suggestions instead of modifying the query.
"""

import calendar
import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class OptimizationResult:
    original_query: str
    optimized_query: str
    hints: list[dict] = field(default_factory=list)

    def add_hint(self, rule: str, message: str, applied: bool) -> None:
        self.hints.append({"rule": rule, "message": message, "applied": applied})


ColumnResolver = Callable[[str], list[str]]


def _replace_select_star(result: OptimizationResult, resolve_columns: ColumnResolver | None) -> None:
    match = re.match(
        r"\s*SELECT\s+\*\s+FROM\s+(`?[A-Za-z_][\w$]*`?)(?!\s*[,])",
        result.optimized_query,
        flags=re.IGNORECASE,
    )
    if not match:
        return
    table = match.group(1).strip("`")
    if not resolve_columns:
        result.add_hint("select-star", "SELECT * reads every column; list only the columns the application needs.", False)
        return
    columns = resolve_columns(table)
    if not columns:
        result.add_hint("select-star", f"Could not resolve columns for {table}; SELECT * was left unchanged.", False)
        return
    quoted = ", ".join(f"`{name.replace('`', '``')}`" for name in columns)
    result.optimized_query = re.sub(r"(?i)^\s*SELECT\s+\*", f"SELECT {quoted}", result.optimized_query, count=1)
    result.add_hint("select-star", "Replaced SELECT * with explicit columns resolved from the schema.", True)


def _rewrite_dates(result: OptimizationResult) -> None:
    pair = re.compile(
        r"YEAR\s*\(\s*([\w.]+)\s*\)\s*=\s*(\d{4})\s+AND\s+MONTH\s*\(\s*\1\s*\)\s*=\s*(\d{1,2})",
        re.IGNORECASE,
    )

    def replace_pair(match: re.Match) -> str:
        column, year, month = match.group(1), int(match.group(2)), int(match.group(3))
        if not (1900 <= year <= 2100 and 1 <= month <= 12):
            return match.group(0)
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        result.add_hint("date-range", "Rewrote YEAR/MONTH predicates as a half-open range that can use an index.", True)
        return f"{column} >= '{year}-{month:02d}-01' AND {column} < '{next_year}-{next_month:02d}-01'"

    result.optimized_query = pair.sub(replace_pair, result.optimized_query)

    year_only = re.compile(r"YEAR\s*\(\s*([\w.]+)\s*\)\s*=\s*(\d{4})", re.IGNORECASE)

    def replace_year(match: re.Match) -> str:
        column, year = match.group(1), int(match.group(2))
        if not 1900 <= year <= 2100:
            return match.group(0)
        result.add_hint("date-range", "Rewrote YEAR() as a half-open date range that can use an index.", True)
        return f"{column} >= '{year}-01-01' AND {column} < '{year + 1}-01-01'"

    result.optimized_query = year_only.sub(replace_year, result.optimized_query)
    if re.search(r"\bMONTH\s*\(", result.optimized_query, re.IGNORECASE):
        result.add_hint("month-predicate", "MONTH() alone cannot be converted to one continuous range without a year constraint.", False)


def _rewrite_prefix_functions(result: OptimizationResult) -> None:
    pattern = re.compile(
        r"(?:LEFT\s*\(\s*([\w.]+)\s*,\s*(\d+)\s*\)|SUBSTR(?:ING)?\s*\(\s*([\w.]+)\s*,\s*1\s*,\s*(\d+)\s*\))\s*=\s*'([^']*)'",
        re.IGNORECASE,
    )

    def replace(match: re.Match) -> str:
        column = match.group(1) or match.group(3)
        length = int(match.group(2) or match.group(4))
        value = match.group(5)
        if len(value) != length or any(char in value for char in ("%", "_", "\\")):
            return match.group(0)
        result.add_hint("prefix-search", "Rewrote a fixed-length prefix function as an index-friendly LIKE prefix.", True)
        return f"{column} LIKE '{value}%'"

    result.optimized_query = pattern.sub(replace, result.optimized_query)


def _add_suggestions(result: OptimizationResult) -> None:
    query = result.optimized_query
    suggestions = [
        (r"\b\w+\s+IN\s*\(\s*SELECT\b", "in-subquery", "Consider a correlated EXISTS after verifying NULL behavior and the execution plan."),
        (r"\bWHERE\b.*\bOR\b", "or-predicate", "OR-to-UNION rewrites can duplicate rows; compare indexed alternatives before changing it."),
        (r"\bDISTINCT\b.*\bGROUP\s+BY\b", "distinct-group", "DISTINCT with GROUP BY may be redundant, but removing it can change grouped output."),
        (r"\bORDER\s+BY\b(?![\s\S]*\bLIMIT\b)", "unbounded-sort", "ORDER BY without LIMIT may require a full sort; add a meaningful product-level limit if appropriate."),
        (r"\bLIKE\s+'%", "leading-wildcard", "A leading wildcard normally prevents use of a B-tree index."),
        (r"\b(?:LOWER|UPPER|TRIM|RIGHT)\s*\(", "non-sargable-function", "A function on an indexed column may prevent an index lookup; consider normalized data or a functional index."),
        (r"\bROUND\s*\(", "round-predicate", "ROUND comparisons require careful boundary and type handling; review a range predicate or functional index."),
        (r"\bINSTR\s*\(", "substring-search", "INSTR substring searches generally cannot use a normal B-tree index."),
        (r"\bCOUNT\s*\(\s*\*\s*\)", "count-star", "COUNT(*) is correct for counting rows; use EXISTS only when the application needs a yes/no answer."),
        (r"\bJOIN\b(?![\s\S]*\bON\b|[\s\S]*\bUSING\b)", "cartesian-join", "JOIN without ON or USING may produce a Cartesian product."),
    ]
    existing = {hint["rule"] for hint in result.hints}
    for pattern, rule, message in suggestions:
        if rule not in existing and re.search(pattern, query, flags=re.IGNORECASE | re.DOTALL):
            result.add_hint(rule, message, False)


def optimize_sql(query: str, resolve_columns: ColumnResolver | None = None) -> OptimizationResult:
    result = OptimizationResult(original_query=query, optimized_query=query.strip())
    _replace_select_star(result, resolve_columns)
    _rewrite_dates(result)
    _rewrite_prefix_functions(result)
    _add_suggestions(result)
    return result

