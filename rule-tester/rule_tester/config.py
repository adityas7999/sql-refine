"""Environment-only MySQL integration configuration."""

from dataclasses import dataclass
import os


ENVIRONMENT_KEYS = (
    "MYSQL_INTEGRATION_HOST",
    "MYSQL_INTEGRATION_PORT",
    "MYSQL_INTEGRATION_USER",
    "MYSQL_INTEGRATION_PASSWORD",
    "MYSQL_INTEGRATION_DATABASE",
)


class ConfigurationError(RuntimeError):
    """A sanitized configuration error that never contains secret values."""


@dataclass(frozen=True, repr=False)
class IntegrationConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_environment(cls) -> "IntegrationConfig":
        values = {key: os.environ.get(key) for key in ENVIRONMENT_KEYS}
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ConfigurationError(
                "Missing required integration environment variables: " + ", ".join(missing)
            )
        try:
            port = int(values["MYSQL_INTEGRATION_PORT"])
        except (TypeError, ValueError) as error:
            raise ConfigurationError("MYSQL_INTEGRATION_PORT must be an integer.") from error
        if not 1 <= port <= 65535:
            raise ConfigurationError("MYSQL_INTEGRATION_PORT must be between 1 and 65535.")
        return cls(
            host=values["MYSQL_INTEGRATION_HOST"],
            port=port,
            user=values["MYSQL_INTEGRATION_USER"],
            password=values["MYSQL_INTEGRATION_PASSWORD"],
            database=values["MYSQL_INTEGRATION_DATABASE"],
        )
