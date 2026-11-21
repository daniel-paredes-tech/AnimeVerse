"""Opening PostgreSQL connections from the settings."""

import psycopg

from animeverse.application.ports import StoreUnavailable
from animeverse.config.settings import DatabaseSettings


def connect(settings: DatabaseSettings) -> psycopg.Connection:
    """Open a connection. A transaction starts automatically on the first query.

    Raises StoreUnavailable if the database cannot be reached. psycopg's
    message names host, port and user, never the password.
    """
    try:
        return psycopg.connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            dbname=settings.dbname,
            sslmode=settings.sslmode,
            connect_timeout=settings.connect_timeout,
        )
    except psycopg.OperationalError as exc:
        raise StoreUnavailable(str(exc).strip()) from exc
