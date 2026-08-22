"""Conservative validation for SQL accepted by the public API."""

import re


class QueryValidationError(ValueError):
    pass


_BLOCKED_KEYWORDS = (
    "ALTER", "CALL", "CREATE", "DELETE", "DO", "DROP", "GRANT", "HANDLER",
    "INSERT", "INTO OUTFILE", "INTO DUMPFILE", "LOAD", "LOCK", "OPTIMIZE",
    "RENAME", "REPAIR", "REPLACE", "REVOKE", "SET", "TRUNCATE", "UNLOCK",
    "UPDATE", "USE",
)


def _strip_comments_and_literals(query: str) -> str:
    query = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
    query = re.sub(r"--[^\n]*|#[^\n]*", " ", query)
    query = re.sub(r"'(?:''|\\.|[^'])*'|\"(?:\"\"|\\.|[^\"])*\"", "''", query)
    return query


def validate_read_only_query(query: object) -> str:
    if not isinstance(query, str) or not query.strip():
        raise QueryValidationError("A non-empty SQL query is required.")
    normalized = query.strip()
    inspected = _strip_comments_and_literals(normalized).strip()
    statements = [part for part in inspected.split(";") if part.strip()]
    if len(statements) != 1:
        raise QueryValidationError("Exactly one SQL statement is allowed.")
    if not re.match(r"^(SELECT|WITH)\b", inspected, flags=re.IGNORECASE):
        raise QueryValidationError("Only SELECT queries and SELECT CTEs are supported.")
    for keyword in _BLOCKED_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", inspected, flags=re.IGNORECASE):
            raise QueryValidationError(f"The statement contains a prohibited operation: {keyword}.")
    return normalized.rstrip(";").strip()

