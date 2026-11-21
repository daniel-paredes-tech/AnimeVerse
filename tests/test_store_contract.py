"""Contract tests: the same checks against the in-memory store and the PostgreSQL store.

The use case tests rely on InMemoryCatalogStore. These tests prove it keeps
the same promises as the real store (idempotent saves, rollback, refusals,
reading order), so a test that passes with the fake means something.

All anime below are made-up test data.
"""

from decimal import Decimal

import pytest

from animeverse.application.ports import RecordRefused
from animeverse.domain.models import Anime, Franchise
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import PostgresCatalogReader, PostgresCatalogStore
from tests.fakes import InMemoryCatalogStore

NARUTO = Franchise("Naruto", "Naruto")
TITAN = Franchise("Attack on Titan", "Attack on Titan")


@pytest.fixture(params=["in-memory", "postgres"])
def store_and_reader(request):
    """(store, reader) for each implementation. Postgres tables are emptied around each test."""
    if request.param == "in-memory":
        store = InMemoryCatalogStore()
        return store, store
    conn = request.getfixturevalue("committing_conn")
    settings = request.getfixturevalue("test_db_settings")
    return PostgresCatalogStore(conn), PostgresCatalogReader(lambda: connect(settings))


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
    assert [a.title for a in reader.anime_by_franchise()["Naruto"]] == ["New title"]


def test_one_anime_can_belong_to_two_franchises(store_and_reader):
    store, reader = store_and_reader
    crossover = Anime(anilist_id=900001, title="Crossover")
    with store.session() as session:
        first = session.save_member(session.save_franchise(NARUTO), crossover)
        second = session.save_member(session.save_franchise(TITAN), crossover)

    assert (first.created, second.created, second.newly_linked) == (True, False, True)
    data = reader.anime_by_franchise()
    assert data["Naruto"] == data["Attack on Titan"] == [crossover]


def test_an_exception_undoes_the_whole_session(store_and_reader):
    store, reader = store_and_reader
    with pytest.raises(RuntimeError), store.session() as session:
        session.save_member(session.save_franchise(NARUTO), Anime(anilist_id=900001, title="Lost"))
        raise RuntimeError("something went wrong")

    assert reader.anime_by_franchise() == {}


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

    assert sorted(a.anilist_id for a in reader.anime_by_franchise()["Naruto"]) == [900001, 900003]


def test_reader_sorts_franchises_by_name_and_anime_by_popularity(store_and_reader):
    store, reader = store_and_reader
    with store.session() as session:
        titan = session.save_franchise(TITAN)
        session.save_franchise(Franchise("Empty", "Empty"))
        session.save_member(titan, Anime(anilist_id=900001, title="Less popular", popularity=10))
        session.save_member(titan, Anime(anilist_id=900002, title="Unknown popularity"))
        session.save_member(titan, Anime(anilist_id=900003, title="More popular", popularity=500))

    data = reader.anime_by_franchise()

    assert list(data) == ["Attack on Titan", "Empty"]
    assert [a.title for a in data["Attack on Titan"]] == ["More popular", "Less popular", "Unknown popularity"]
    assert data["Empty"] == []
