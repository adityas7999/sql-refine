"""Small database access layer used by the analyzer and optimizer."""

from contextlib import contextmanager

import pymysql


@contextmanager
def connection(config: dict, *, streaming: bool = False):
    db = pymysql.connect(
        **config,
        cursorclass=pymysql.cursors.SSCursor if streaming else pymysql.cursors.Cursor,
        autocommit=True,
    )
    try:
        yield db
    finally:
        db.close()


def get_columns(config: dict, table_name: str) -> list[str]:
    """Return columns for one table without interpolating identifiers into SQL."""
    with connection(config) as db, db.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (config["database"], table_name),
        )
        return [row[0] for row in cursor.fetchall()]

