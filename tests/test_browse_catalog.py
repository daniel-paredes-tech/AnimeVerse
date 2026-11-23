"""Tests for the BrowseCatalog use case, with the in-memory store: no database.

All anime below are made-up test data.
"""

import pytest

from animeverse.application.catalog import MAX_PAGE_SIZE, BrowseCatalog
from animeverse.application.errors import AnimeNotFound, InvalidQuery, NotFound
from animeverse.application.ports import AnimeFilters, PageRequest, Sort, StoreUnavailable
from animeverse.domain.models import Anime, Franchise
from tests.fakes import InMemoryCatalogStore


@pytest.fixture
def store() -> InMemoryCatalogStore:
    store = InMemoryCatalogStore()
    with store.session() as session:
        naruto = session.save_franchise(Franchise("Naruto", "Naruto"))
        session.save_member(naruto, Anime(anilist_id=900001, title="Naruto", episodes=220, popularity=10))
        session.save_member(naruto, Anime(anilist_id=900002, title="Boruto", episodes=293, popularity=5))
    return store


def test_list_anime_returns_a_page_from_the_store(store):
    page = BrowseCatalog(store).list_anime(AnimeFilters(), Sort(), PageRequest(1, 24))

    assert [a.anime.title for a in page.items] == ["Naruto", "Boruto"]
    assert page.total_items == 2


def test_get_anime_returns_the_anime(store):
    anime_id = store.list_anime(AnimeFilters(), Sort(), PageRequest()).items[0].id

    assert BrowseCatalog(store).get_anime(anime_id).anime.title == "Naruto"


def test_get_anime_raises_not_found_for_an_unknown_id(store):
    with pytest.raises(AnimeNotFound) as caught:
        BrowseCatalog(store).get_anime(999)

    assert isinstance(caught.value, NotFound)  # the API maps every NotFound to 404
    assert str(caught.value) == "There is no anime with id 999."


def test_list_franchises(store):
    franchises = BrowseCatalog(store).list_franchises()

    assert [(f.name, f.anime_count) for f in franchises] == [("Naruto", 2)]


@pytest.mark.parametrize(
    ("filters", "page", "expected"),
    [
        pytest.param(AnimeFilters(year_from=2010, year_to=2000), PageRequest(), ("year_to", "too_small"), id="years"),
        pytest.param(AnimeFilters(), PageRequest(0, 24), ("page", "too_small"), id="page 0"),
        pytest.param(AnimeFilters(), PageRequest(1, 0), ("page_size", "too_small"), id="page size 0"),
        pytest.param(AnimeFilters(), PageRequest(1, MAX_PAGE_SIZE + 1), ("page_size", "too_large"), id="page size"),
    ],
)
def test_an_impossible_query_is_refused_before_reaching_the_store(store, filters, page, expected):
    store.unavailable = True  # proves the store is never asked

    with pytest.raises(InvalidQuery) as caught:
        BrowseCatalog(store).list_anime(filters, Sort(), page)

    assert [(v.field, v.code) for v in caught.value.violations] == [expected]


def test_the_same_year_for_both_ends_is_fine(store):
    BrowseCatalog(store).list_anime(AnimeFilters(year_from=2002, year_to=2002), Sort(), PageRequest())


def test_store_unavailable_is_passed_on(store):
    store.unavailable = True

    with pytest.raises(StoreUnavailable):
        BrowseCatalog(store).list_franchises()
