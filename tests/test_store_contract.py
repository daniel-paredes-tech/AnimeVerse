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

from animeverse.application.ports import AnimeFilters, CatalogQuery, PageRequest, RecordRefused, Sort
from animeverse.domain.models import Anime, Franchise
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import PostgresCatalogQuery, PostgresCatalogStore
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
