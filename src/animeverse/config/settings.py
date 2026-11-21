"""Configuration loaded from environment variables.

Values come from the real environment or, if not set there, from the .env file
in the project root (variables already set in the environment take priority).
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


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


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        # Name the missing variable, never print a value.
        raise ConfigError(f"Missing required setting {name}. Add it to .env (see .env.example).")
    return value


def load_database_settings() -> DatabaseSettings:
    """Read the PostgreSQL connection settings."""
    load_dotenv()

    port_text = os.environ.get("POSTGRES_PORT", "5432")
    try:
        port = int(port_text)
    except ValueError:
        raise ConfigError(f"POSTGRES_PORT must be a number, got {port_text!r}.") from None

    return DatabaseSettings(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=port,
        user=_require("POSTGRES_USER"),
        dbname=_require("POSTGRES_DB"),
        password=_require("POSTGRES_PASSWORD"),
    )
