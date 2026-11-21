"""The CatalogStore and CatalogReader ports, implemented with PostgreSQL.

The SQL itself is in repository.py; this module adds the unit of work and
translates psycopg's errors into the errors the ports declare:

- a value PostgreSQL cannot store, or a broken constraint (DataError,
  IntegrityError)                                    -> RecordRefused
- anything else (connection lost, server down...)    -> StoreUnavailable
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg

from animeverse.application.ports import RecordRefused, SavedMember, StoreUnavailable
from animeverse.domain.models import Anime, Franchise
from animeverse.infrastructure.postgres import repository


class PostgresCatalogStore:
    """CatalogStore on one open connection. Each session is one transaction."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    @contextmanager
    def session(self) -> Iterator["PostgresCatalogSession"]:
        try:
            # Commits when the block ends normally, rolls back if it raises.
            with self._conn.transaction():
                yield PostgresCatalogSession(self._conn)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc


class PostgresCatalogSession:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def save_franchise(self, franchise: Franchise) -> int:
        try:
            return repository.upsert_franchise(self._conn, franchise)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc

    def save_member(self, franchise_id: int, anime: Anime) -> SavedMember:
        try:
            # A savepoint: if PostgreSQL refuses this anime, only this anime is
            # undone and the transaction stays usable for the others.
            with self._conn.transaction():
                saved = repository.upsert_anime(self._conn, anime)
                newly_linked = repository.link_anime_to_franchise(self._conn, saved.id, franchise_id)
        except (psycopg.DataError, psycopg.IntegrityError) as exc:
            raise RecordRefused(_first_line(exc)) from exc
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc
        return SavedMember(created=saved.created, newly_linked=newly_linked)


class PostgresCatalogReader:
    """CatalogReader that opens a fresh connection for every read (fine for a local page)."""

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def anime_by_franchise(self) -> dict[str, list[Anime]]:
        try:
            with self._connect() as conn:
                return repository.list_anime_by_franchise(conn)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc


def _first_line(exc: Exception) -> str:
    """psycopg messages can span several lines (DETAIL, HINT); the first one says what happened."""
    return str(exc).splitlines()[0] if str(exc) else type(exc).__name__
