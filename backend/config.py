"""Production-safe, environment-backed application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


def _integer(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    return max(minimum, value)


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = _integer("MAX_REQUEST_BYTES", 262_144)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    CONNECTION_SESSION_TTL_SECONDS = _integer("CONNECTION_SESSION_TTL_SECONDS", 1800)
    MAX_CONNECTION_SESSIONS = _integer("MAX_CONNECTION_SESSIONS", 100)
    DB_CONNECT_TIMEOUT_SECONDS = _integer("DB_CONNECT_TIMEOUT_SECONDS", 5)
    DB_READ_TIMEOUT_SECONDS = _integer("DB_READ_TIMEOUT_SECONDS", 30)
    DB_WRITE_TIMEOUT_SECONDS = _integer("DB_WRITE_TIMEOUT_SECONDS", 10)
    STATEMENT_TIMEOUT_MS = _integer("STATEMENT_TIMEOUT_MS", 10_000)
    RUNTIME_SAMPLES = min(_integer("RUNTIME_SAMPLES", 3), 9)
    RUNTIME_WARMUPS = min(_integer("RUNTIME_WARMUPS", 1, 0), 3)
    SCHEMA_MAX_TABLES = _integer("SCHEMA_MAX_TABLES", 500)
    SCHEMA_MAX_COLUMNS = _integer("SCHEMA_MAX_COLUMNS", 10_000)
    MYSQL_SSL_CA = os.getenv("MYSQL_SSL_CA", "").strip() or None
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "120 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
