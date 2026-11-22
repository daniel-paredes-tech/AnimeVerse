"""The storage ports, implemented with PostgreSQL.

    CatalogStore, CatalogReader  (the importer and the old page)   SQL in repository.py
    CatalogQuery                 (browsing, for the API)            SQL in catalog_queries.py
    WatchlistStore               (the user's watchlist)             SQL in watchlist_repository.py

This module adds the units of work and translates psycopg's errors into the
errors the ports declare:

- a value PostgreSQL cannot store, or a broken constraint (DataError,
  IntegrityError)                                    -> RecordRefused
- anything else (connection lost, server down...)    -> StoreUnavailable
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg

from animeverse.application.ports import (
    AnimeFilters,
    CatalogAnime,
    FranchiseCount,
    Page,
    PageRequest,
    RecordRefused,
    SavedEntry,
    SavedMember,
    Sort,
    StoreUnavailable,
)
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry
from animeverse.infrastructure.postgres import catalog_queries, repository, watchlist_repository


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


class PostgresCatalogQuery:
    """CatalogQuery with a fresh connection per call (fine for a local, single-user API).

    Under real load a connection pool would avoid reconnecting each time.
    """

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def list_anime(self, filters: AnimeFilters, sort: Sort, page: PageRequest) -> Page[CatalogAnime]:
        try:
            with self._connect() as conn:
                return catalog_queries.list_anime(conn, filters, sort, page)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc

    def get_anime(self, anime_id: int) -> CatalogAnime | None:
        try:
            with self._connect() as conn:
                return catalog_queries.get_anime(conn, anime_id)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc

    def list_franchises(self) -> list[FranchiseCount]:
        try:
            with self._connect() as conn:
                return catalog_queries.list_franchises(conn)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc


class PostgresWatchlistStore:
    """WatchlistStore: each call is one transaction on a fresh connection.

    `with conn:` commits when the block ends normally and rolls back if it raises.
    """

    def __init__(self, connect: Callable[[], psycopg.Connection]) -> None:
        self._connect = connect

    def save(self, anime_id: int, entry: WatchlistEntry) -> SavedEntry:
        try:
            with self._connect() as conn:
                return watchlist_repository.upsert_entry(conn, anime_id, entry)
        except (psycopg.DataError, psycopg.IntegrityError) as exc:
            # A CHECK constraint, or a missing anime (foreign key).
            raise RecordRefused(_first_line(exc)) from exc
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc

    def delete(self, anime_id: int) -> bool:
        try:
            with self._connect() as conn:
                return watchlist_repository.delete_entry(conn, anime_id)
        except psycopg.Error as exc:
            raise StoreUnavailable(_first_line(exc)) from exc


def _first_line(exc: Exception) -> str:
    """psycopg messages can span several lines (DETAIL, HINT); the first one says what happened."""
    return str(exc).splitlines()[0] if str(exc) else type(exc).__name__
