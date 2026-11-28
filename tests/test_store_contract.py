"""Contract tests: the same checks against the in-memory store and the PostgreSQL store.

The use case tests rely on InMemoryCatalogStore. These tests prove it keeps
the same promises as the real store (idempotent saves, rollback, refusals,
reading order), so a test that passes with the fake means something.

What the importer saves is read back through CatalogQuery, the port the API
reads from, so these tests also prove that imported data is what the API shows.

All anime below are made-up test data.
"""

from decimal import Decimal

import pytest

from animeverse.application.ports import (
    AnimeFilters,
    CatalogQuery,
    PageRequest,
    RecordRefused,
    Sort,
    UnlinkedAnime,
)
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import (
    PostgresCatalogQuery,
    PostgresCatalogStore,
    PostgresWatchlistStore,
)
from tests.fakes import InMemoryCatalogStore

NARUTO = Franchise("Naruto", "Naruto")
TITAN = Franchise("Attack on Titan", "Attack on Titan")


@pytest.fixture(params=["in-memory", "postgres"])
def store_and_reader(request):
    """(store, query) for each implementation. Postgres tables are emptied around each test."""
    if request.param == "in-memory":
        store = InMemoryCatalogStore()
        return store, store
    conn = request.getfixturevalue("committing_conn")
    settings = request.getfixturevalue("test_db_settings")
    return PostgresCatalogStore(conn), PostgresCatalogQuery(lambda: connect(settings))


def anime_of(query: CatalogQuery, franchise_name: str) -> list[Anime]:
    """The franchise's anime, in the default order (most popular first, unknown popularity last)."""
    franchise = next(f for f in query.list_franchises() if f.name == franchise_name)
    page = query.list_anime(AnimeFilters(franchise_id=franchise.id), Sort(), PageRequest(1, 100))
    return [item.anime for item in page.items]


def total_anime(query: CatalogQuery) -> int:
    return query.list_anime(AnimeFilters(), Sort(), PageRequest()).total_items


def test_saving_twice_refreshes_instead_of_duplicating(store_and_reader):
    store, reader = store_and_reader
    with store.session() as session:
        franchise_id = session.save_franchise(NARUTO)
        first = session.save_member(franchise_id, Anime(anilist_id=900001, title="Old title"))
    with store.session() as session:
        franchise_id = session.save_franchise(NARUTO)
        second = session.save_member(franchise_id, Anime(anilist_id=900001, title="New title"))

    assert (first.created, first.newly_linked) == (True, True)
    assert (second.created, second.newly_linked) == (False, False)
    assert [a.title for a in anime_of(reader, "Naruto")] == ["New title"]
    assert total_anime(reader) == 1


def test_one_anime_can_belong_to_two_franchises(store_and_reader):
    store, reader = store_and_reader
    crossover = Anime(anilist_id=900001, title="Crossover")
    with store.session() as session:
        first = session.save_member(session.save_franchise(NARUTO), crossover)
        second = session.save_member(session.save_franchise(TITAN), crossover)

    assert (first.created, second.created, second.newly_linked) == (True, False, True)
    assert anime_of(reader, "Naruto") == anime_of(reader, "Attack on Titan") == [crossover]
    assert total_anime(reader) == 1  # one anime, linked twice


def test_an_exception_undoes_the_whole_session(store_and_reader):
    store, reader = store_and_reader
    with pytest.raises(RuntimeError), store.session() as session:
        session.save_member(session.save_franchise(NARUTO), Anime(anilist_id=900001, title="Lost"))
        raise RuntimeError("something went wrong")

    assert reader.list_franchises() == []
    assert total_anime(reader) == 0


@pytest.mark.parametrize(
    "bad",
    [
        Anime(anilist_id=900002, title="Bad", episodes=-1),
        Anime(anilist_id=900002, title="Bad", popularity=-5),
        Anime(anilist_id=900002, title="Bad", score=Decimal("11")),
        Anime(anilist_id=900002, title="Bad", start_year=0),
    ],
)
def test_a_refused_anime_leaves_the_rest_of_the_session_usable(store_and_reader, bad):
    store, reader = store_and_reader
    with store.session() as session:
        franchise_id = session.save_franchise(NARUTO)
        session.save_member(franchise_id, Anime(anilist_id=900001, title="Good"))
        with pytest.raises(RecordRefused):
            session.save_member(franchise_id, bad)
        session.save_member(franchise_id, Anime(anilist_id=900003, title="Also good"))

    assert sorted(a.anilist_id for a in anime_of(reader, "Naruto")) == [900001, 900003]


def test_franchises_are_listed_by_name_and_anime_by_popularity(store_and_reader):
    store, reader = store_and_reader
    with store.session() as session:
        titan = session.save_franchise(TITAN)
        session.save_franchise(Franchise("Empty", "Empty"))
        session.save_member(titan, Anime(anilist_id=900001, title="Less popular", popularity=10))
        session.save_member(titan, Anime(anilist_id=900002, title="Unknown popularity"))
        session.save_member(titan, Anime(anilist_id=900003, title="More popular", popularity=500))

    franchises = reader.list_franchises()

    assert [(f.name, f.anime_count) for f in franchises] == [("Attack on Titan", 3), ("Empty", 0)]
    assert [a.title for a in anime_of(reader, "Attack on Titan")] == [
        "More popular",
        "Less popular",
        "Unknown popularity",
    ]


# --- Keeping only a franchise's members (link reconciliation) -------------------------


@pytest.fixture(params=["in-memory", "postgres"])
def store_reader_watchlist(request):
    """(store, query, watchlist) for each implementation."""
    if request.param == "in-memory":
        store = InMemoryCatalogStore()
        return store, store, store
    conn = request.getfixturevalue("committing_conn")
    settings = request.getfixturevalue("test_db_settings")
    return (
        PostgresCatalogStore(conn),
        PostgresCatalogQuery(lambda: connect(settings)),
        PostgresWatchlistStore(lambda: connect(settings)),
    )


def save_members(store, franchise: Franchise, *anilist_ids: int) -> int:
    """Save the anime as members of the franchise, in one session. Returns the franchise id."""
    with store.session() as session:
        franchise_id = session.save_franchise(franchise)
        for anilist_id in anilist_ids:
            session.save_member(franchise_id, Anime(anilist_id=anilist_id, title=f"Anime {anilist_id}"))
    return franchise_id


def keep_only(store, franchise_id: int, *anilist_ids: int) -> list[UnlinkedAnime]:
    with store.session() as session:
        return session.keep_only_links(franchise_id, frozenset(anilist_ids))


def stored(query: CatalogQuery) -> dict[int, list[str]]:
    """Every stored anime: AniList id -> names of its franchises."""
    page = query.list_anime(AnimeFilters(), Sort(), PageRequest(1, 100))
    return {item.anime.anilist_id: [f.name for f in item.franchises] for item in page.items}


def test_keep_only_links_removes_other_links_and_deletes_orphans(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)

    unlinked = keep_only(store, naruto, 900001)

    assert unlinked == [UnlinkedAnime(900002, "Anime 900002", deleted=True)]
    assert stored(reader) == {900001: ["Naruto"]}


def test_an_anime_still_in_another_franchise_is_not_deleted(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)
    save_members(store, TITAN, 900002)

    unlinked = keep_only(store, naruto, 900001)

    assert unlinked == [UnlinkedAnime(900002, "Anime 900002", deleted=False)]
    assert stored(reader) == {900001: ["Naruto"], 900002: ["Attack on Titan"]}


def test_an_anime_in_the_watchlist_is_kept(store_reader_watchlist):
    store, reader, watchlist = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)
    anime_id = next(
        item.id
        for item in reader.list_anime(AnimeFilters(), Sort(), PageRequest()).items
        if item.anime.anilist_id == 900002
    )
    entry = WatchlistEntry(WatchStatus("watching"), 3, None, None)
    watchlist.save(anime_id, entry)

    unlinked = keep_only(store, naruto, 900001)

    assert unlinked == [UnlinkedAnime(900002, "Anime 900002", deleted=False)]
    assert stored(reader) == {900001: ["Naruto"], 900002: []}
    kept = reader.get_anime(anime_id)
    assert kept is not None and kept.watchlist_entry is not None and kept.watchlist_entry.entry == entry


def test_keep_only_links_with_every_member_kept_changes_nothing(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)

    assert keep_only(store, naruto, 900001, 900002, 900099) == []  # 900099: not stored, ignored
    assert stored(reader) == {900001: ["Naruto"], 900002: ["Naruto"]}


def test_keep_only_links_leaves_other_franchises_alone(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001)
    save_members(store, TITAN, 900010)

    assert keep_only(store, naruto, 900001) == []
    assert stored(reader) == {900001: ["Naruto"], 900010: ["Attack on Titan"]}


def test_unlinked_anime_are_listed_by_anilist_id(store_reader_watchlist):
    store, _, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900003, 900001, 900002)

    assert [u.anilist_id for u in keep_only(store, naruto)] == [900001, 900002, 900003]


def test_keep_only_links_is_undone_with_the_session(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)

    with pytest.raises(RuntimeError), store.session() as session:
        session.keep_only_links(naruto, frozenset({900001}))
        raise RuntimeError("something went wrong")

    assert stored(reader) == {900001: ["Naruto"], 900002: ["Naruto"]}


def test_an_anime_saved_after_a_deletion_gets_an_id_of_its_own(store_reader_watchlist):
    store, reader, _ = store_reader_watchlist
    naruto = save_members(store, NARUTO, 900001, 900002)
    keep_only(store, naruto, 900002)  # deletes 900001

    save_members(store, NARUTO, 900002, 900003)

    ids = [item.id for item in reader.list_anime(AnimeFilters(), Sort(), PageRequest()).items]
    assert len(ids) == 2 and len(set(ids)) == 2
