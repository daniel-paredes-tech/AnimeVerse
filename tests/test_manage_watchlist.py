"""Tests for the ManageWatchlist use case, with the in-memory store: no database.

All anime below are made-up test data.
"""

import pytest

from animeverse.application.errors import AnimeNotFound, InvalidWatchlistEntry, NotFound, WatchlistEntryNotFound
from animeverse.application.watchlist import ManageWatchlist
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from tests.fakes import InMemoryCatalogStore

WATCHING = WatchlistEntry(WatchStatus.WATCHING, episodes_watched=12, rating=8, notes="Good so far.")


@pytest.fixture
def store() -> InMemoryCatalogStore:
    store = InMemoryCatalogStore()
    with store.session() as session:
        franchise = session.save_franchise(Franchise("Test", "Test"))
        session.save_member(franchise, Anime(anilist_id=900001, title="Test Anime", episodes=24))
    return store


@pytest.fixture
def anime_id(store) -> int:
    return store.anime_id_of(900001)


def test_saving_a_new_entry_creates_it(store, anime_id):
    saved = ManageWatchlist(store, store).save(anime_id, WATCHING)

    assert saved.created is True
    assert saved.stored.anime_id == anime_id
    assert saved.stored.entry == WATCHING
    assert store.get_anime(anime_id).watchlist_entry.entry == WATCHING


def test_saving_again_replaces_the_entry(store, anime_id):
    watchlist = ManageWatchlist(store, store)
    first = watchlist.save(anime_id, WATCHING)
    done = WatchlistEntry(WatchStatus.COMPLETED, episodes_watched=24, rating=10, notes=None)

    second = watchlist.save(anime_id, done)

    assert second.created is False
    assert second.stored.entry == done
    assert second.stored.created_at == first.stored.created_at  # replaced, not re-created
    assert store.get_anime(anime_id).watchlist_entry.entry == done


def test_blank_notes_are_saved_as_none(store, anime_id):
    saved = ManageWatchlist(store, store).save(anime_id, WatchlistEntry(WatchStatus.WATCHING, 1, None, "   "))

    assert saved.stored.entry.notes is None


def test_an_entry_that_breaks_the_rules_is_refused_and_not_saved(store, anime_id):
    too_many = WatchlistEntry(WatchStatus.WATCHING, episodes_watched=25, rating=None, notes=None)

    with pytest.raises(InvalidWatchlistEntry) as caught:
        ManageWatchlist(store, store).save(anime_id, too_many)

    assert [(v.field, v.code) for v in caught.value.violations] == [("episodes_watched", "exceeds_episodes")]
    assert store.get_anime(anime_id).watchlist_entry is None


def test_saving_for_an_unknown_anime_is_not_found(store):
    with pytest.raises(AnimeNotFound) as caught:
        ManageWatchlist(store, store).save(999, WATCHING)

    assert isinstance(caught.value, NotFound)


def test_removing_an_entry(store, anime_id):
    watchlist = ManageWatchlist(store, store)
    watchlist.save(anime_id, WATCHING)

    watchlist.remove(anime_id)

    assert store.get_anime(anime_id).watchlist_entry is None


def test_removing_a_missing_entry_is_not_found(store, anime_id):
    with pytest.raises(WatchlistEntryNotFound) as caught:
        ManageWatchlist(store, store).remove(anime_id)

    assert isinstance(caught.value, NotFound)
    assert str(caught.value) == f"The anime with id {anime_id} is not on your watchlist."


def test_removing_from_an_unknown_anime_is_not_found(store):
    with pytest.raises(AnimeNotFound):
        ManageWatchlist(store, store).remove(999)


class ImportDeletesTheAnimeAfterItIsRead:
    """A CatalogQuery that, right after each read, lets an import delete the anime (ADR 0012)."""

    def __init__(self, store: InMemoryCatalogStore) -> None:
        self._store = store

    def get_anime(self, anime_id: int):
        found = self._store.get_anime(anime_id)
        franchise_id = self._store.committed.franchises["Test"][0]
        with self._store.session() as session:
            session.keep_only_links(franchise_id, frozenset())  # it no longer belongs: deleted
        return found


def test_an_anime_deleted_by_an_import_mid_save_is_not_found(store, anime_id):
    watchlist = ManageWatchlist(ImportDeletesTheAnimeAfterItIsRead(store), store)

    with pytest.raises(AnimeNotFound):
        watchlist.save(anime_id, WATCHING)
