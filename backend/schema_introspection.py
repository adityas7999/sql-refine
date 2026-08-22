"""Parameterized INFORMATION_SCHEMA discovery for the active MySQL account."""

from errors import DatabaseAccessError
from security import validate_identifier

_SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}


def list_databases(connection) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute("SHOW DATABASES")
        return [
            {"name": row[0], "system": row[0].lower() in _SYSTEM_DATABASES}
            for row in cursor.fetchall()
        ]


def inspect_schema(connection, database: str, *, max_tables: int = 500, max_columns: int = 10_000) -> dict:
    database = validate_identifier(database, "database name")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS, TABLE_COMMENT
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
            LIMIT %s
            """,
            (database, max_tables + 1),
        )
        table_rows = cursor.fetchall()
        tables_truncated = len(table_rows) > max_tables
        table_rows = table_rows[:max_tables]

        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, DATA_TYPE,
                   IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            LIMIT %s
            """,
            (database, max_columns + 1),
        )
        column_rows = cursor.fetchall()
        columns_truncated = len(column_rows) > max_columns
        column_rows = column_rows[:max_columns]

        cursor.execute(
            """
            SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME,
                   COLLATION, CARDINALITY, INDEX_TYPE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
            LIMIT %s
            """,
            (database, max_columns),
        )
        index_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME,
                   REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
            LIMIT %s
            """,
            (database, max_columns),
        )
        relationship_rows = cursor.fetchall()

    if not table_rows and not any(item["name"] == database for item in list_databases(connection)):
        raise DatabaseAccessError("The selected database does not exist or is not accessible.", "DATABASE_NOT_ACCESSIBLE", 403)

    table_map = {
        row[0]: {
            "name": row[0], "type": row[1], "engine": row[2], "estimatedRows": row[3],
            "comment": row[4] or "", "columns": [], "indexes": [], "relationships": [],
        }
        for row in table_rows
    }
    for row in column_rows:
        if row[0] in table_map:
            table_map[row[0]]["columns"].append({
                "name": row[1], "position": row[2], "columnType": row[3], "dataType": row[4],
                "nullable": row[5] == "YES", "default": row[6], "key": row[7],
                "extra": row[8], "comment": row[9] or "",
            })
    grouped_indexes: dict[tuple[str, str], dict] = {}
    for row in index_rows:
        if row[0] not in table_map:
            continue
        key = (row[0], row[1])
        grouped_indexes.setdefault(key, {
            "name": row[1], "unique": not bool(row[2]), "type": row[7], "columns": [],
        })["columns"].append({"name": row[4], "sequence": row[3], "cardinality": row[6], "collation": row[5]})
    for (table_name, _), index in grouped_indexes.items():
        table_map[table_name]["indexes"].append(index)
    for row in relationship_rows:
        if row[0] in table_map:
            table_map[row[0]]["relationships"].append({
                "column": row[1], "constraint": row[2],
                "referencedTable": row[3], "referencedColumn": row[4],
            })
    return {
        "database": database, "tables": list(table_map.values()),
        "truncated": {"tables": tables_truncated, "columns": columns_truncated},
    }


def table_columns(connection, database: str, table: str) -> list[dict]:
    database = validate_identifier(database, "database name")
    table = validate_identifier(table, "table name")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (database, table),
        )
        return [{"name": row[0], "dataType": row[1], "extra": row[2]} for row in cursor.fetchall()]
