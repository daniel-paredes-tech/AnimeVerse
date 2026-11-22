"""Tests for the PostgreSQL adapter's error translation (the rest is in the contract tests)."""

import psycopg
import pytest

from animeverse.application.ports import AnimeFilters, PageRequest, Sort, StoreUnavailable
from animeverse.domain.models import Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import (
    PostgresCatalogQuery,
    PostgresCatalogReader,
    PostgresCatalogStore,
    PostgresWatchlistStore,
)


def test_unreachable_database_becomes_store_unavailable():
    def refuse() -> psycopg.Connection:
        raise psycopg.OperationalError("connection refused")

    with pytest.raises(StoreUnavailable, match="connection refused"):
        PostgresCatalogReader(refuse).anime_by_franchise()


def test_lost_connection_becomes_store_unavailable(test_db_settings):
    conn = connect(test_db_settings)
    conn.close()  # as if the server had gone away

    with pytest.raises(StoreUnavailable), PostgresCatalogStore(conn).session() as session:
        session.save_franchise(Franchise("Naruto", "Naruto"))


# --- The API's adapters: CatalogQuery and WatchlistStore --------------------------------


def _refuse() -> psycopg.Connection:
    raise psycopg.OperationalError("connection refused")


@pytest.mark.parametrize(
    "call",
    [
        lambda connect_: PostgresCatalogQuery(connect_).list_anime(AnimeFilters(), Sort(), PageRequest()),
        lambda connect_: PostgresCatalogQuery(connect_).get_anime(1),
        lambda connect_: PostgresCatalogQuery(connect_).list_franchises(),
        lambda connect_: PostgresWatchlistStore(connect_).save(1, WatchlistEntry(WatchStatus.WATCHING, 0, None, None)),
        lambda connect_: PostgresWatchlistStore(connect_).delete(1),
    ],
    ids=["list_anime", "get_anime", "list_franchises", "save", "delete"],
)
def test_api_adapters_turn_an_unreachable_database_into_store_unavailable(call):
    with pytest.raises(StoreUnavailable, match="connection refused"):
        call(_refuse)


def test_api_adapters_turn_a_lost_connection_into_store_unavailable(test_db_settings):
    conn = connect(test_db_settings)
    conn.close()  # as if the server had gone away mid-request

    with pytest.raises(StoreUnavailable):
        PostgresCatalogQuery(lambda: conn).list_franchises()
