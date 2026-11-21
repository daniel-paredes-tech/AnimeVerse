"""Run the Alembic migrations from Python (used by `animeverse migrate` and the tests)."""

from pathlib import Path

import sqlalchemy.exc
from alembic import command
from alembic.config import Config

from animeverse.application.ports import StoreUnavailable
from animeverse.config.settings import DatabaseSettings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(settings: DatabaseSettings) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["database_settings"] = settings  # read by migrations/env.py
    return config


def upgrade_to_latest(settings: DatabaseSettings) -> None:
    """Apply every migration the database doesn't have yet. Safe to run any number of times.

    Raises StoreUnavailable if the database cannot be reached.
    """
    try:
        command.upgrade(alembic_config(settings), "head")
    except sqlalchemy.exc.OperationalError as exc:
        raise StoreUnavailable(str(exc.orig).strip() if exc.orig else str(exc)) from exc
