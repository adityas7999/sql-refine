"""Conservative, educational MySQL optimization rules.

Only transformations proven safe for the supplied schema context are applied. All
other opportunities remain suggestions with explicit safety classifications.
"""

import re
from dataclasses import dataclass, field
from typing import Callable

ColumnResolver = Callable[[str], list[str]]
ColumnTypeResolver = Callable[[str], str | None]
_TEMPORAL_TYPES = {"date", "datetime", "timestamp"}


@dataclass
class OptimizationResult:
    original_query: str
    optimized_query: str
    suggestions: list[dict] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.optimized_query.strip() != self.original_query.strip()

    def add(self, rule: str, message: str, *, applied: bool, severity: str, safety: str, affected_sql: str | None = None) -> None:
        self.suggestions.append({
            "rule": rule, "message": message, "applied": applied,
            "severity": severity, "safety": safety, "affectedSql": affected_sql,
        })


def _select_star(result: OptimizationResult, resolve_columns: ColumnResolver | None) -> None:
    match = re.match(r"\s*SELECT\s+\*\s+FROM\s+(`?[A-Za-z_][\w$-]*`?)\s*(?:;)?$", result.optimized_query, re.IGNORECASE)
    if not match:
        if re.search(r"\bSELECT\s+(?:\w+\.)?\*", result.optimized_query, re.IGNORECASE):
            result.add("select-star", "SELECT * can transfer unnecessary columns. Expansion is not automatic for joins, aliases, or complex projections.", applied=False, severity="info", safety="context-dependent", affected_sql="SELECT *")
        return
    table = match.group(1).strip("`")
    columns = resolve_columns(table) if resolve_columns else []
    if not columns:
        result.add("select-star", "SELECT * reads every visible column; schema metadata was unavailable, so it was not changed.", applied=False, severity="info", safety="context-dependent", affected_sql=match.group(0))
        return
    quoted = ", ".join(f"`{column.replace('`', '``')}`" for column in columns)
    result.optimized_query = re.sub(r"(?i)^\s*SELECT\s+\*", f"SELECT {quoted}", result.optimized_query, count=1)
    result.add("select-star", "Expanded SELECT * using the selected table's visible columns.", applied=True, severity="info", safety="safe", affected_sql="SELECT *")


def _date_ranges(result: OptimizationResult, resolve_type: ColumnTypeResolver | None) -> None:
    pair = re.compile(r"YEAR\s*\(\s*([\w.]+)\s*\)\s*=\s*(\d{4})\s+AND\s+MONTH\s*\(\s*\1\s*\)\s*=\s*(\d{1,2})", re.IGNORECASE)
    year_only = re.compile(r"YEAR\s*\(\s*([\w.]+)\s*\)\s*=\s*(\d{4})", re.IGNORECASE)

    def pair_replacement(match: re.Match) -> str:
        column, year, month = match.group(1), int(match.group(2)), int(match.group(3))
        data_type = (resolve_type(column) if resolve_type else None) or ""
        if not (1900 <= year <= 2100 and 1 <= month <= 12 and data_type.lower() in _TEMPORAL_TYPES):
            result.add("date-range", "A half-open date range may be sargable, but the column could not be proven to be DATE, DATETIME, or TIMESTAMP.", applied=False, severity="warning", safety="context-dependent", affected_sql=match.group(0))
            return match.group(0)
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        result.add("date-range", "Rewrote YEAR/MONTH predicates as a half-open range after verifying the temporal column type.", applied=True, severity="info", safety="safe", affected_sql=match.group(0))
        return f"{column} >= '{year}-{month:02d}-01' AND {column} < '{next_year}-{next_month:02d}-01'"

    result.optimized_query = pair.sub(pair_replacement, result.optimized_query)

    def year_replacement(match: re.Match) -> str:
        column, year = match.group(1), int(match.group(2))
        data_type = (resolve_type(column) if resolve_type else None) or ""
        if not (1900 <= year <= 2100 and data_type.lower() in _TEMPORAL_TYPES):
            result.add("date-range", "YEAR() can prevent an index range scan; a half-open rewrite requires a verified temporal column.", applied=False, severity="warning", safety="context-dependent", affected_sql=match.group(0))
            return match.group(0)
        result.add("date-range", "Rewrote YEAR() as a half-open range after verifying the temporal column type.", applied=True, severity="info", safety="safe", affected_sql=match.group(0))
        return f"{column} >= '{year}-01-01' AND {column} < '{year + 1}-01-01'"

    result.optimized_query = year_only.sub(year_replacement, result.optimized_query)


def _suggestions(result: OptimizationResult) -> None:
    rules = [
        (r"\b\w+\s+IN\s*\(\s*SELECT\b", "in-subquery", "EXISTS may perform better, but NULL behavior and correlation must be verified.", "warning", "unsafe"),
        (r"\bWHERE\b.*\bOR\b", "or-predicate", "Separate indexed branches may help, but UNION ALL can introduce duplicates.", "warning", "unsafe"),
        (r"\bDISTINCT\b.*\bGROUP\s+BY\b", "distinct-group", "DISTINCT may be redundant, but removing it can collapse results differently across groups.", "warning", "unsafe"),
        (r"\bORDER\s+BY\b(?![\s\S]*\bLIMIT\b)", "unbounded-sort", "ORDER BY without a product-level limit may sort the complete result set.", "info", "context-dependent"),
        (r"\bLIKE\s+'%", "leading-wildcard", "A leading wildcard normally prevents a B-tree index range lookup.", "warning", "suggestion-only"),
        (r"\b(?:LOWER|UPPER|TRIM|RIGHT|SUBSTR(?:ING)?|LEFT)\s*\(", "non-sargable-function", "A function on an indexed column may require a scan; consider normalized data or a functional index.", "info", "context-dependent"),
        (r"\bROUND\s*\(", "round-predicate", "ROUND predicates require type- and boundary-aware handling; consider a functional index or verified range.", "info", "context-dependent"),
        (r"\bINSTR\s*\(", "substring-search", "INSTR searches generally cannot use a normal B-tree index.", "info", "suggestion-only"),
        (r"\bCOUNT\s*\(\s*\*\s*\)", "count-star", "COUNT(*) is correct for row counts; use EXISTS only if the application needs a yes/no answer.", "info", "context-dependent"),
        (r"\bJOIN\b(?![\s\S]*\bON\b|[\s\S]*\bUSING\b)", "cartesian-join", "JOIN without ON or USING may create a Cartesian product.", "critical", "unsafe"),
    ]
    existing = {item["rule"] for item in result.suggestions}
    for pattern, rule, message, severity, safety in rules:
        match = re.search(pattern, result.optimized_query, re.IGNORECASE | re.DOTALL)
        if match and rule not in existing:
            result.add(rule, message, applied=False, severity=severity, safety=safety, affected_sql=match.group(0)[:240])


def optimize_sql(query: str, resolve_columns: ColumnResolver | None = None, resolve_column_type: ColumnTypeResolver | None = None) -> OptimizationResult:
    result = OptimizationResult(original_query=query, optimized_query=query.strip())
    _select_star(result, resolve_columns)
    _date_ranges(result, resolve_column_type)
    _suggestions(result)
    return result

