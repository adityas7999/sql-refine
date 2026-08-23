"""Validated, expiring, in-memory MySQL credential sessions."""

import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

import pymysql

from errors import ConnectionSessionError, DatabaseAccessError, QueryTimeoutError, ValidationError
from security import validate_identifier


@dataclass(repr=False)
class ConnectionSettings:
    name: str
    host: str
    port: int
    username: str
    password: str
    default_database: str | None
    ssl_enabled: bool
    ssl_verify_certificate: bool


@dataclass
class SessionRecord:
    settings: ConnectionSettings
    created_at: float
    last_used_at: float


def parse_connection_settings(payload: object) -> ConnectionSettings:
    if not isinstance(payload, dict):
        raise ValidationError("Connection details must be a JSON object.")
    name = str(payload.get("name") or "MySQL connection").strip()[:80]
    host = str(payload.get("host") or "").strip()
    username = str(payload.get("username") or "").strip()
    password = payload.get("password")
    database = str(payload.get("database") or "").strip() or None
    if not host or len(host) > 255 or any(char.isspace() for char in host):
        raise ValidationError("A valid MySQL host is required.", "INVALID_CONNECTION")
    if not username or len(username) > 128:
        raise ValidationError("A valid MySQL username is required.", "INVALID_CONNECTION")
    if not isinstance(password, str):
        raise ValidationError("A MySQL password value is required.", "INVALID_CONNECTION")
    try:
        port = int(payload.get("port", 3306))
    except (TypeError, ValueError) as error:
        raise ValidationError("The MySQL port must be a number.", "INVALID_CONNECTION") from error
    if not 1 <= port <= 65535:
        raise ValidationError("The MySQL port must be between 1 and 65535.", "INVALID_CONNECTION")
    if database:
        validate_identifier(database, "database name")
    return ConnectionSettings(
        name=name or "MySQL connection", host=host, port=port, username=username,
        password=password, default_database=database,
        ssl_enabled=bool(payload.get("sslEnabled", False)),
        ssl_verify_certificate=bool(payload.get("sslVerifyCertificate", True)),
    )


class ConnectionManager:
    def __init__(self, config):
        self._ttl = config["CONNECTION_SESSION_TTL_SECONDS"]
        self._max_sessions = config["MAX_CONNECTION_SESSIONS"]
        self._connect_timeout = config["DB_CONNECT_TIMEOUT_SECONDS"]
        self._read_timeout = config["DB_READ_TIMEOUT_SECONDS"]
        self._write_timeout = config["DB_WRITE_TIMEOUT_SECONDS"]
        self._statement_timeout_ms = config["STATEMENT_TIMEOUT_MS"]
        self._ssl_ca = config.get("MYSQL_SSL_CA")
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def _purge_expired(self) -> None:
        cutoff = time.monotonic() - self._ttl
        expired = [key for key, record in self._sessions.items() if record.last_used_at < cutoff]
        for key in expired:
            self._sessions.pop(key, None)

    def create_session(self, settings: ConnectionSettings) -> str:
        with self._lock:
            self._purge_expired()
            if len(self._sessions) >= self._max_sessions:
                oldest = min(self._sessions, key=lambda key: self._sessions[key].last_used_at)
                self._sessions.pop(oldest, None)
            session_id = secrets.token_urlsafe(32)
            now = time.monotonic()
            self._sessions[session_id] = SessionRecord(settings=settings, created_at=now, last_used_at=now)
            return session_id

    def get_settings(self, session_id: str | None) -> ConnectionSettings:
        if not session_id:
            raise ConnectionSessionError()
        with self._lock:
            self._purge_expired()
            record = self._sessions.get(session_id)
            if not record:
                raise ConnectionSessionError()
            record.last_used_at = time.monotonic()
            return record.settings

    def delete_session(self, session_id: str | None) -> None:
        if session_id:
            with self._lock:
                self._sessions.pop(session_id, None)

    def is_ready(self) -> bool:
        return self._lock is not None

    def _connect_kwargs(self, settings: ConnectionSettings, database: str | None) -> dict:
        ssl = None
        if settings.ssl_enabled:
            ssl = {"check_hostname": settings.ssl_verify_certificate}
            if self._ssl_ca:
                ssl["ca"] = self._ssl_ca
        return {
            "host": settings.host, "port": settings.port, "user": settings.username,
            "password": settings.password, "database": database or settings.default_database,
            "connect_timeout": self._connect_timeout, "read_timeout": self._read_timeout,
            "write_timeout": self._write_timeout, "charset": "utf8mb4", "autocommit": True,
            "cursorclass": pymysql.cursors.Cursor, "ssl": ssl,
        }

    @contextmanager
    def connect(self, session_id: str, database: str | None = None):
        settings = self.get_settings(session_id)
        if database:
            validate_identifier(database, "database name")
        connection = None
        try:
            connection = pymysql.connect(**self._connect_kwargs(settings, database))
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME = %s", (self._statement_timeout_ms,))
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
            yield connection
        except pymysql.err.OperationalError as error:
            if error.args and error.args[0] in {1969, 3024}:
                raise QueryTimeoutError() from error
            if error.args and error.args[0] in {1044, 1045, 1142, 1227}:
                raise DatabaseAccessError("The MySQL account does not have permission for this operation.", "PERMISSION_DENIED", 403) from error
            if error.args and error.args[0] == 1049:
                raise DatabaseAccessError("The selected database does not exist or is not accessible.", "DATABASE_NOT_ACCESSIBLE", 404) from error
            raise DatabaseAccessError() from error
        except pymysql.MySQLError as error:
            raise DatabaseAccessError() from error
        finally:
            if connection is not None:
                connection.close()

    def test(self, settings: ConnectionSettings) -> dict:
        connection = None
        try:
            connection = pymysql.connect(**self._connect_kwargs(settings, settings.default_database))
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
            return {"serverVersion": version}
        except pymysql.MySQLError as error:
            raise DatabaseAccessError("MySQL rejected the connection. Verify the host, TLS settings, account, and permissions.", "CONNECTION_FAILED") from error
        finally:
            if connection is not None:
                connection.close()
