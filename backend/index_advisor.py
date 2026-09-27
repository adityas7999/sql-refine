"""Conservative, read-only index suggestions for simple MySQL predicates."""

from sqlglot import exp, parse_one

from security import validate_identifier

_INDEXABLE_TYPES = {
    "tinyint", "smallint", "mediumint", "int", "integer", "bigint",
    "decimal", "float", "double", "date", "datetime", "timestamp",
    "time", "year", "char", "varchar",
}
_COMPARISONS = (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE)


def _literal(node):
    return isinstance(node, (exp.Literal, exp.Null))


def _column(node, table_names):
    if not isinstance(node, exp.Column):
        return None
    if node.table and node.table.lower() not in table_names:
        return None
    return node.name


def _predicate_column(node, table_names):
    if isinstance(node, _COMPARISONS):
        return (_column(node.left, table_names) if _literal(node.right) else None) or (
            _column(node.right, table_names) if _literal(node.left) else None
        )
    if isinstance(node, exp.Between) and _literal(node.args.get("low")) and _literal(node.args.get("high")):
        return _column(node.this, table_names)
    if isinstance(node, exp.In) and node.expressions and all(_literal(item) for item in node.expressions):
        return _column(node.this, table_names)
    if isinstance(node, exp.Is) and isinstance(node.expression, exp.Null):
        return _column(node.this, table_names)
    return None


def _conjuncts(node):
    if isinstance(node, exp.And):
        return _conjuncts(node.left) + _conjuncts(node.right)
    return [node]


def suggest_indexes(connection, database: str, query: str) -> list[dict]:
    """Suggest only full-column BTREE keys absent from simple single-table queries.

    This checks index eligibility, not selectivity or an observed speedup. It
    never issues DDL and skips ambiguous SQL instead of guessing ownership.
    """
    expression = parse_one(query, read="mysql")
    if not isinstance(expression, exp.Select) or expression.find(exp.Join, exp.Subquery, exp.With, exp.Or):
        return []
    tables = list(expression.find_all(exp.Table))
    if len(tables) != 1 or not expression.args.get("where"):
        return []
    table = tables[0]
    if table.db and table.db.lower() != database.lower():
        return []
    table_name = validate_identifier(table.name, "table name")
    names = {table_name.lower()}
    if table.alias:
        names.add(table.alias.lower())
    predicates = _conjuncts(expression.args["where"].this)
    requested = {name.lower() for node in predicates if (name := _predicate_column(node, names))}
    if not requested:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (database, table_name),
        )
        columns = {
            name.lower(): (name, data_type.lower(), length)
            for name, data_type, length in cursor.fetchall()
        }
        cursor.execute(
            """
            SELECT COLUMN_NAME, INDEX_TYPE, SUB_PART, IS_VISIBLE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND SEQ_IN_INDEX = 1
            """,
            (database, table_name),
        )
        leading_parts = {}
        for name, kind, prefix, visible in cursor.fetchall():
            if name and kind.upper() == "BTREE":
                leading_parts.setdefault(name.lower(), []).append((prefix, visible))
        leading = {
            name for name, parts in leading_parts.items()
            if any(prefix is None and visible == "YES" for prefix, visible in parts)
        }

    suggestions = []
    for name in sorted(requested - leading):
        metadata = columns.get(name)
        if not metadata:
            continue
        actual_name, data_type, length = metadata
        if data_type not in _INDEXABLE_TYPES or (
            data_type in {"char", "varchar"} and (length is None or length > 191)
        ):
            continue
        existing = leading_parts.get(name, [])
        if any(prefix is None and visible != "YES" for prefix, visible in existing):
            action = "A full-column index exists but is invisible; review its visibility and the query plan before adding another."
        elif any(prefix is not None for prefix, _visible in existing):
            action = "A prefix index exists; check its selectivity and plan before considering a full-column index."
        else:
            action = "An index beginning with this column may support the direct filter; check selectivity and EXPLAIN against the workload before creating one."
        suggestions.append({
            "rule": "missing-index", "applied": False, "severity": "info",
            "safety": "schema-dependent",
            "table": table_name, "column": actual_name,
            "affectedSql": f"{table_name}({actual_name})",
            "message": (
                f"No visible full-column BTREE index starts with {table_name}.{actual_name}. "
                f"{action} Indexes consume storage and add write overhead."
            ),
        })
    return suggestions
