"""Opening PostgreSQL connections from the settings."""

import psycopg

from animeverse.config.settings import DatabaseSettings


def connect(settings: DatabaseSettings) -> psycopg.Connection:
    """Open a connection. A transaction starts automatically on the first query."""
    return psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.dbname,
    )
