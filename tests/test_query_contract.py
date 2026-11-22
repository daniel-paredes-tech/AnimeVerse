"""Contract tests for CatalogQuery and WatchlistStore: the same checks for every implementation.

The use case tests rely on the in-memory store. These tests pin down what
the ports promise (filters, sort order, pages, watchlist saves), so the
PostgreSQL adapters can be held to exactly the same behaviour.

All anime below are made-up test data.
"""

from decimal import Decimal

import pytest

from animeverse.application.ports import AnimeFilters, PageRequest, RecordRefused, Sort, SortField
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from tests.fakes import InMemoryCatalogStore

ALPHA = Anime(
    anilist_id=900001,
    title="Alpha",
    title_english="First One",
    title_japanese="アルファ",
    type="TV",
    status="FINISHED",
    episodes=24,
    start_year=2002,
    score=Decimal("8.00"),
    popularity=100,
)
BETA = Anime(
    anilist_id=900002,
    title="beta",
    type="MOVIE",
    status="RELEASING",
    start_year=2010,
    score=Decimal("7.50"),
    popularity=300,
)
GAMMA = Anime(anilist_id=900003, title="Gamma 100%", type="TV", status="FINISHED")  # no year, score or popularity
DELTA = Anime(
    anilist_id=900004,
    title="Delta",
    type="TV",
    status="NOT_YET_RELEASED",
    start_year=2010,
    score=Decimal("7.50"),
    popularity=300,  # the same popularity and score as BETA: ties are broken by id
)


class Catalog:
    """The ports under test, plus helpers to fill them."""

    def __init__(self, store, query, watchlist) -> None:
        self.store, self.query, self.watchlist = store, query, watchlist

    def titles(self, filters=None, sort=None, page=None) -> list[str]:
        result = self.query.list_anime(filters or AnimeFilters(), sort or Sort(), page or PageRequest())
        return [a.anime.title for a in result.items]

    def id_of(self, title: str) -> int:
        return next(
            a.id
            for a in self.query.list_anime(AnimeFilters(), Sort(), PageRequest(1, 100)).items
            if a.anime.title == title
        )


@pytest.fixture(params=["in-memory"])
def catalog(request) -> Catalog:
    """An implementation filled with ALPHA..DELTA: Naruto (Alpha, beta), Attack on Titan (beta, Gamma)."""
    store = InMemoryCatalogStore()
    catalog = Catalog(store, store, store)
    with store.session() as session:
        naruto = session.save_franchise(Franchise("Naruto", "Naruto"))
        titan = session.save_franchise(Franchise("Attack on Titan", "Attack on Titan"))
        session.save_franchise(Franchise("Bleach", "Bleach"))  # no anime
        session.save_member(naruto, ALPHA)
        session.save_member(naruto, BETA)
        session.save_member(titan, BETA)
        session.save_member(titan, GAMMA)
        session.save_member(naruto, DELTA)
    return catalog


def watching(episodes: int = 1) -> WatchlistEntry:
    return WatchlistEntry(WatchStatus.WATCHING, episodes, rating=None, notes=None)


# --- Sorting ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        (Sort(SortField.POPULARITY, descending=True), ["beta", "Delta", "Alpha", "Gamma 100%"]),
        (Sort(SortField.POPULARITY, descending=False), ["Alpha", "beta", "Delta", "Gamma 100%"]),
        (Sort(SortField.SCORE, descending=True), ["Alpha", "beta", "Delta", "Gamma 100%"]),
        (Sort(SortField.SCORE, descending=False), ["beta", "Delta", "Alpha", "Gamma 100%"]),
        (Sort(SortField.START_YEAR, descending=False), ["Alpha", "beta", "Delta", "Gamma 100%"]),
        (Sort(SortField.START_YEAR, descending=True), ["beta", "Delta", "Alpha", "Gamma 100%"]),
        (Sort(SortField.TITLE, descending=False), ["Alpha", "beta", "Delta", "Gamma 100%"]),  # ignoring case
        (Sort(SortField.TITLE, descending=True), ["Gamma 100%", "Delta", "beta", "Alpha"]),
    ],
    ids=lambda v: f"{'-' if v.descending else ''}{v.field}" if isinstance(v, Sort) else "",
)
def test_sort_puts_missing_values_last_and_breaks_ties_by_id(catalog, sort, expected):
    assert catalog.titles(sort=sort) == expected


# --- Filters ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        pytest.param(AnimeFilters(text="ALPH"), ["Alpha"], id="romaji title, ignoring case"),
        pytest.param(AnimeFilters(text="first"), ["Alpha"], id="English title"),
        pytest.param(AnimeFilters(text="アル"), ["Alpha"], id="Japanese title"),
        pytest.param(AnimeFilters(text="100%"), ["Gamma 100%"], id="percent sign"),
        pytest.param(AnimeFilters(text="%"), ["Gamma 100%"], id="% is literal, not a wildcard"),
        pytest.param(AnimeFilters(text="_"), [], id="_ is literal, not a wildcard"),
        pytest.param(AnimeFilters(franchise_id=2), ["beta", "Gamma 100%"], id="franchise"),
        pytest.param(AnimeFilters(status="RELEASING"), ["beta"], id="status"),
        pytest.param(AnimeFilters(format="MOVIE"), ["beta"], id="format"),
        pytest.param(AnimeFilters(year_from=2005), ["beta", "Delta"], id="year from (no year: left out)"),
        pytest.param(AnimeFilters(year_to=2005), ["Alpha"], id="year to"),
        pytest.param(AnimeFilters(year_from=2010, year_to=2010), ["beta", "Delta"], id="one year"),
        pytest.param(AnimeFilters(min_score=Decimal("7.6")), ["Alpha"], id="min score"),
        pytest.param(AnimeFilters(min_score=Decimal("7.5")), ["beta", "Delta", "Alpha"], id="min score inclusive"),
        pytest.param(AnimeFilters(franchise_id=1, year_from=2005), ["beta", "Delta"], id="filters combine with AND"),
        pytest.param(AnimeFilters(text="zzz"), [], id="nothing matches"),
    ],
)
def test_filters(catalog, filters, expected):
    assert catalog.titles(filters, Sort(SortField.POPULARITY, descending=True)) == expected


def test_franchise_ids_follow_creation_order(catalog):
    # The filter tests above use franchise ids 1 (Naruto) and 2 (Attack on Titan).
    assert [(f.id, f.name) for f in catalog.query.list_franchises()] == [
        (2, "Attack on Titan"),
        (3, "Bleach"),
        (1, "Naruto"),
    ]


def test_watchlist_filters(catalog):
    catalog.watchlist.save(catalog.id_of("Alpha"), watching())
    catalog.watchlist.save(catalog.id_of("Delta"), WatchlistEntry(WatchStatus.PLANNING, 0, None, None))

    assert catalog.titles(AnimeFilters(on_watchlist=True)) == ["Delta", "Alpha"]
    assert catalog.titles(AnimeFilters(on_watchlist=False)) == ["beta", "Gamma 100%"]
    assert catalog.titles(AnimeFilters(watchlist_status=WatchStatus.PLANNING)) == ["Delta"]
    assert catalog.titles(AnimeFilters(watchlist_status=WatchStatus.DROPPED)) == []


# --- Pages --------------------------------------------------------------------------------


def test_pages(catalog):
    first = catalog.query.list_anime(AnimeFilters(), Sort(), PageRequest(1, 3))
    second = catalog.query.list_anime(AnimeFilters(), Sort(), PageRequest(2, 3))
    past_the_end = catalog.query.list_anime(AnimeFilters(), Sort(), PageRequest(3, 3))

    assert [a.anime.title for a in first.items] == ["beta", "Delta", "Alpha"]
    assert [a.anime.title for a in second.items] == ["Gamma 100%"]
    assert past_the_end.items == []
    assert first.total_items == second.total_items == past_the_end.total_items == 4
    assert first.total_pages == 2


def test_total_counts_only_matches(catalog):
    page = catalog.query.list_anime(AnimeFilters(format="TV"), Sort(), PageRequest(1, 1))

    assert (len(page.items), page.total_items, page.total_pages) == (1, 3, 3)


def test_an_empty_result_has_zero_pages(catalog):
    page = catalog.query.list_anime(AnimeFilters(text="zzz"), Sort(), PageRequest())

    assert (page.items, page.total_items, page.total_pages) == ([], 0, 0)


# --- One anime and the franchise list -------------------------------------------------------


def test_get_anime_returns_every_field_and_its_franchises_alphabetically(catalog):
    beta = catalog.query.get_anime(catalog.id_of("beta"))

    assert beta.anime == BETA
    assert [f.name for f in beta.franchises] == ["Attack on Titan", "Naruto"]
    assert beta.watchlist_entry is None
    assert beta.updated_at is not None


def test_get_anime_returns_none_for_an_unknown_id(catalog):
    assert catalog.query.get_anime(999_999) is None


def test_list_franchises_counts_anime_and_includes_empty_ones(catalog):
    counts = {f.name: f.anime_count for f in catalog.query.list_franchises()}

    assert counts == {"Attack on Titan": 2, "Bleach": 0, "Naruto": 3}


# --- The watchlist store -------------------------------------------------------------------


def test_saving_creates_then_replaces(catalog):
    anime_id = catalog.id_of("Alpha")
    first = catalog.watchlist.save(anime_id, watching(1))
    done = WatchlistEntry(WatchStatus.COMPLETED, 24, rating=9, notes="Loved it.")

    second = catalog.watchlist.save(anime_id, done)

    assert (first.created, second.created) == (True, False)
    assert second.stored.entry == done
    assert second.stored.anime_id == anime_id
    assert second.stored.created_at == first.stored.created_at
    assert second.stored.updated_at >= first.stored.updated_at
    assert catalog.query.get_anime(anime_id).watchlist_entry == second.stored


def test_deleting(catalog):
    anime_id = catalog.id_of("Alpha")
    catalog.watchlist.save(anime_id, watching())

    assert catalog.watchlist.delete(anime_id) is True
    assert catalog.watchlist.delete(anime_id) is False
    assert catalog.query.get_anime(anime_id).watchlist_entry is None


def test_saving_for_a_missing_anime_is_refused(catalog):
    with pytest.raises(RecordRefused):
        catalog.watchlist.save(999_999, watching())


@pytest.mark.parametrize(
    "bad",
    [
        WatchlistEntry(WatchStatus.WATCHING, -1, None, None),
        WatchlistEntry(WatchStatus.WATCHING, 0, 11, None),
        WatchlistEntry(WatchStatus.WATCHING, 0, None, "x" * 1001),
        WatchlistEntry(WatchStatus.WATCHING, 0, None, "  "),
    ],
    ids=["negative episodes", "rating 11", "notes too long", "blank notes"],
)
def test_values_the_table_cannot_hold_are_refused(catalog, bad):
    anime_id = catalog.id_of("Alpha")

    with pytest.raises(RecordRefused):
        catalog.watchlist.save(anime_id, bad)

    assert catalog.query.get_anime(anime_id).watchlist_entry is None
