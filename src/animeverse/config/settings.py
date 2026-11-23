"""Configuration loaded from environment variables.

Values come from the real environment or, if not set there, from the .env file
in the project root (variables already set in the environment take priority).
In the cloud the same variables are set by the platform (for example from a
secrets manager), so the code does not change. .env.example lists them all.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# PostgreSQL's sslmode values. "prefer" (the default) uses SSL when the server
# offers it; a managed database in the cloud (e.g. AWS RDS) should use "require"
# or stronger.
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(Exception):
    """Raised when a required setting is missing or invalid."""


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    dbname: str
    # repr=False keeps the password out of printed objects, logs and tracebacks.
    password: str = field(repr=False)
    sslmode: str = "prefer"
    connect_timeout: int = 10  # seconds to wait for the database to answer a new connection


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        # Name the missing variable, never print a value.
        raise ConfigError(f"Missing required setting {name}. Add it to .env (see .env.example).")
    return value


def _positive_int(name: str, default: int) -> int:
    text = os.environ.get(name, str(default))
    try:
        value = int(text)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {text!r}.") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {value}.")
    return value


def _choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = os.environ.get(name, default)
    if value not in allowed:
        raise ConfigError(f"{name} must be one of {', '.join(allowed)}; got {value!r}.")
    return value


def load_database_settings() -> DatabaseSettings:
    """Read the PostgreSQL connection settings."""
    load_dotenv()
    return DatabaseSettings(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=_positive_int("POSTGRES_PORT", 5432),
        user=_require("POSTGRES_USER"),
        dbname=_require("POSTGRES_DB"),
        password=_require("POSTGRES_PASSWORD"),
        sslmode=_choice("POSTGRES_SSLMODE", "prefer", SSL_MODES),
        connect_timeout=_positive_int("POSTGRES_CONNECT_TIMEOUT", 10),
    )


def load_openapi_path() -> Path:
    """Where the API contract is (OPENAPI_PATH, default openapi.yaml in the current folder).

    The API serves this file at /v1/openapi.yaml. Raises ConfigError if it doesn't exist.
    """
    load_dotenv()
    path = Path(os.environ.get("OPENAPI_PATH", "openapi.yaml"))
    if not path.is_file():
        raise ConfigError(
            f"The API contract was not found at {path}. Run the command from the project folder, or set OPENAPI_PATH."
        )
    return path


def load_web_dist() -> Path | None:
    """The built web UI (WEB_DIST_DIR, default web/dist), or None if it hasn't been built.

    Without it, `animeverse serve` serves the API only; build the UI with
    `npm run build` in web/.
    """
    load_dotenv()
    path = Path(os.environ.get("WEB_DIST_DIR", "web/dist"))
    return path if (path / "index.html").is_file() else None


def load_log_level() -> str:
    """The logging level, from LOG_LEVEL (default INFO)."""
    load_dotenv()
    return _choice("LOG_LEVEL", "INFO", LOG_LEVELS)
