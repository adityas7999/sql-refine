"""Environment-backed application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


def _database_config(database_name: str) -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": database_name,
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
        "read_timeout": int(os.getenv("DB_READ_TIMEOUT", "30")),
        "write_timeout": int(os.getenv("DB_WRITE_TIMEOUT", "30")),
        "charset": "utf8mb4",
    }


class Config:
    ORIGINAL_DB = _database_config(os.getenv("ORIGINAL_DB_NAME", "testdb"))
    OPTIMIZED_DB = _database_config(os.getenv("OPTIMIZED_DB_NAME", "testdb_copy"))
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

