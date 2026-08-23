"""Bounded MySQL operations used by the local tester."""

from contextlib import contextmanager
import hashlib
import json

import pymysql

from .bootstrap import BACKEND_ROOT  # noqa: F401
from analyzer import parse_json_plan


class QueryExecutionFailure(RuntimeError):
    """Sanitized execution failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@contextmanager
def connect(config, *, timeout_seconds: int):
    connection = None
    try:
        connection = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=timeout_seconds,
            read_timeout=timeout_seconds,
            write_timeout=timeout_seconds,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.execute("SET SESSION MAX_EXECUTION_TIME = %s", (timeout_seconds * 1000,))
        yield connection
    except pymysql.err.OperationalError as error:
        code = "QUERY_TIMEOUT" if error.args and error.args[0] in {3024, 1317} else "MYSQL_OPERATION_FAILED"
        raise QueryExecutionFailure(code) from None
    except pymysql.MySQLError:
        raise QueryExecutionFailure("MYSQL_OPERATION_FAILED") from None
    finally:
        if connection is not None:
            connection.close()


def execute_complete(connection, query: str, *, max_rows: int):
    from .models import QueryOutput

    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            description = cursor.description or ()
            columns = tuple((str(item[0]), int(item[1])) for item in description)
            rows = tuple(cursor.fetchmany(max_rows + 1))
    except pymysql.err.OperationalError as error:
        code = "QUERY_TIMEOUT" if error.args and error.args[0] in {3024, 1317} else "QUERY_FAILED"
        raise QueryExecutionFailure(code) from None
    except pymysql.MySQLError:
        raise QueryExecutionFailure("QUERY_FAILED") from None
    return QueryOutput(columns=columns, rows=rows[:max_rows], truncated=len(rows) > max_rows)


def explain_cost(connection, query: str) -> float | None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN FORMAT=JSON " + query)
            row = cursor.fetchone()
        if not row:
            raise QueryExecutionFailure("EMPTY_PLAN")
        return parse_json_plan(row[0]).get("estimatedCost")
    except QueryExecutionFailure:
        raise
    except pymysql.err.OperationalError as error:
        code = "QUERY_TIMEOUT" if error.args and error.args[0] in {3024, 1317} else "EXPLAIN_FAILED"
        raise QueryExecutionFailure(code) from None
    except pymysql.MySQLError:
        raise QueryExecutionFailure("EXPLAIN_FAILED") from None


def mysql_version(connection) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"


def schema_index_fingerprint(connection, database: str) -> str:
    statement = """
        SELECT table_name, column_name, ordinal_position, data_type,
               is_nullable, column_key, extra
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position
    """
    indexes = """
        SELECT table_name, index_name, non_unique, seq_in_index,
               column_name, collation, sub_part
        FROM information_schema.statistics
        WHERE table_schema = %s
        ORDER BY table_name, index_name, seq_in_index
    """
    with connection.cursor() as cursor:
        cursor.execute(statement, (database,))
        column_rows = cursor.fetchall()
        cursor.execute(indexes, (database,))
        index_rows = cursor.fetchall()
    encoded = json.dumps(
        {"columns": column_rows, "indexes": index_rows},
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def table_columns(connection, database: str, table: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (database, table),
        )
        return [str(row[0]) for row in cursor.fetchall()]


def column_type(connection, database: str, table: str, column: str) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = %s
            """,
            (database, table, column),
        )
        row = cursor.fetchone()
    return str(row[0]) if row else None
