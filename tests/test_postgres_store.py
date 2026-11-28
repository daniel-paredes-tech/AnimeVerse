"""Tests for the PostgreSQL adapter: error translation and concurrency (the rest is in the contract tests)."""

import threading
import time

import psycopg
import pytest

from animeverse.application.ports import AnimeFilters, PageRequest, Sort, StoreUnavailable
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import (
    PostgresCatalogQuery,
    PostgresCatalogStore,
    PostgresWatchlistStore,
)


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


# --- Concurrency: an import reconciling links while the API writes the watchlist ------------


def test_a_watchlist_entry_saved_during_reconciliation_is_never_lost(committing_conn, test_db_settings):
    """The API saves an entry for an anime the import is about to delete as an orphan.

    The API's insert holds a lock on the anime (foreign key check) when the import's
    delete arrives. Whatever the timing, the committed entry and its anime must survive.
    """
    store = PostgresCatalogStore(committing_conn)
    with store.session() as session:
        franchise_id = session.save_franchise(Franchise("Naruto", "Naruto"))
        session.save_member(franchise_id, Anime(anilist_id=900001, title="About to be orphaned"))
    anime_id = committing_conn.execute("SELECT id FROM anime WHERE anilist_id = 900001").fetchone()[0]

    api = connect(test_db_settings)
    try:
        api.execute("INSERT INTO watchlist_entries (anime_id, status) VALUES (%s, 'planning')", (anime_id,))
        # Not committed yet: the import must wait for it.
        result = {}
        importer = threading.Thread(
            target=lambda: result.update(unlinked=_keep_nothing(store, franchise_id)), daemon=True
        )
        importer.start()
        time.sleep(0.5)
        assert importer.is_alive(), "the import should be waiting for the API's lock"
        api.commit()
        importer.join(timeout=10)
    finally:
        api.close()

    assert not importer.is_alive()
    assert [(u.anilist_id, u.deleted) for u in result["unlinked"]] == [(900001, False)]
    with connect(test_db_settings) as check:
        assert check.execute("SELECT count(*) FROM watchlist_entries").fetchone()[0] == 1
        assert check.execute("SELECT count(*) FROM anime").fetchone()[0] == 1


def _keep_nothing(store: PostgresCatalogStore, franchise_id: int):
    with store.session() as session:
        return session.keep_only_links(franchise_id, frozenset())
