import time
from unittest.mock import patch

import pymysql
import pytest

from connection_manager import ConnectionManager, parse_connection_settings
from errors import ConnectionSessionError, DatabaseAccessError, QueryTimeoutError, ValidationError


CONFIG = {
    "CONNECTION_SESSION_TTL_SECONDS": 30, "MAX_CONNECTION_SESSIONS": 2,
    "DB_CONNECT_TIMEOUT_SECONDS": 2, "DB_READ_TIMEOUT_SECONDS": 3,
    "DB_WRITE_TIMEOUT_SECONDS": 3, "STATEMENT_TIMEOUT_MS": 500,
    "MYSQL_SSL_CA": None,
}


def settings():
    return parse_connection_settings({"name": "dev", "host": "localhost", "port": 3306, "username": "reader", "password": "secret"})


def test_connection_payload_validation():
    with pytest.raises(ValidationError):
        parse_connection_settings({"host": "bad host", "port": 70000, "username": "", "password": "x"})


def test_session_is_ephemeral_and_deletable():
    manager = ConnectionManager(CONFIG)
    session_id = manager.create_session(settings())
    assert manager.get_settings(session_id).password == "secret"
    manager.delete_session(session_id)
    with pytest.raises(ConnectionSessionError):
        manager.get_settings(session_id)


def test_connection_settings_repr_never_exposes_password():
    connection_settings = settings()
    assert "secret" not in repr(connection_settings)


class TimeoutCursor:
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, *_args): raise pymysql.err.OperationalError(3024, "timeout")


class TimeoutConnection:
    def cursor(self): return TimeoutCursor()
    def close(self): pass


def test_timeout_is_sanitized_and_connection_is_closed():
    manager = ConnectionManager(CONFIG)
    session_id = manager.create_session(settings())
    with patch("connection_manager.pymysql.connect", return_value=TimeoutConnection()):
        with pytest.raises(QueryTimeoutError):
            with manager.connect(session_id):
                pass


class ErrorCursor(TimeoutCursor):
    def execute(self, *_args): raise pymysql.err.OperationalError(1044, "secret database detail")


class ErrorConnection(TimeoutConnection):
    def cursor(self): return ErrorCursor()


def test_permission_error_is_classified_without_database_detail():
    manager = ConnectionManager(CONFIG)
    session_id = manager.create_session(settings())
    with patch("connection_manager.pymysql.connect", return_value=ErrorConnection()):
        with pytest.raises(DatabaseAccessError) as caught:
            with manager.connect(session_id):
                pass
    assert caught.value.code == "PERMISSION_DENIED"
    assert "secret database detail" not in caught.value.message
