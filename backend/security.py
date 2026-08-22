"""AST-backed policy for untrusted MySQL queries and identifiers."""

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from errors import ValidationError

MAX_QUERY_CHARACTERS = 50_000
_COMMENT_MARKERS = ("--", "#", "/*", "*/")
_DANGEROUS_FUNCTIONS = {
    "BENCHMARK", "GET_LOCK", "IS_FREE_LOCK", "IS_USED_LOCK", "LOAD_FILE",
    "MASTER_POS_WAIT", "RELEASE_ALL_LOCKS", "RELEASE_LOCK", "SLEEP",
    "SYS_EXEC", "SYS_EVAL",
}
def validate_identifier(value: object, label: str = "identifier") -> str:
    if not isinstance(value, str) or not value or len(value) > 64 or value != value.strip():
        raise ValidationError(f"Invalid {label}.", "INVALID_IDENTIFIER")
    if any(ord(character) < 32 or character == "\x7f" for character in value):
        raise ValidationError(f"Invalid {label}.", "INVALID_IDENTIFIER")
    return value


def quote_identifier(value: object, label: str = "identifier") -> str:
    return f"`{validate_identifier(value, label).replace('`', '``')}`"


def validate_read_only_query(query: object) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("A non-empty SQL query is required.", "INVALID_QUERY")
    normalized = query.strip()
    if len(normalized) > MAX_QUERY_CHARACTERS:
        raise ValidationError("The SQL query is too large.", "QUERY_TOO_LARGE")
    if any(marker in normalized for marker in _COMMENT_MARKERS):
        raise ValidationError("SQL comments are not accepted.", "COMMENTS_NOT_ALLOWED")
    try:
        statements = [statement for statement in parse(normalized, read="mysql") if statement is not None]
    except ParseError as error:
        raise ValidationError("The SQL query could not be parsed as MySQL.", "INVALID_SQL") from error
    if len(statements) != 1:
        raise ValidationError("Exactly one SQL statement is allowed.", "MULTIPLE_STATEMENTS")

    statement = statements[0]
    if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise ValidationError("Only read-only SELECT queries and SELECT CTEs are supported.", "READ_ONLY_REQUIRED")

    prohibited_nodes = tuple(
        node for node in (
            getattr(exp, "Alter", None), getattr(exp, "Call", None), getattr(exp, "Command", None),
            getattr(exp, "Create", None), getattr(exp, "Delete", None), getattr(exp, "Drop", None),
            getattr(exp, "Execute", None), getattr(exp, "Grant", None), getattr(exp, "Insert", None),
            getattr(exp, "Into", None), getattr(exp, "LoadData", None), getattr(exp, "Lock", None),
            getattr(exp, "Merge", None), getattr(exp, "Set", None), getattr(exp, "Transaction", None),
            getattr(exp, "TruncateTable", None), getattr(exp, "Update", None), getattr(exp, "Use", None),
        ) if node is not None
    )
    if prohibited_nodes and any(statement.find_all(*prohibited_nodes)):
        raise ValidationError("The query contains a prohibited operation or locking clause.", "DANGEROUS_SQL")

    for function in statement.find_all(exp.Anonymous):
        if function.name.upper() in _DANGEROUS_FUNCTIONS:
            raise ValidationError(f"The function {function.name.upper()} is not allowed.", "DANGEROUS_FUNCTION")
    return normalized.rstrip(";").strip()
