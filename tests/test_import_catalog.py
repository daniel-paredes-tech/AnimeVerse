"""Tests for the import use case, with in-memory fakes: no network, no database.

All anime below are made-up test data.
"""

from animeverse.application.import_catalog import ImportCatalog
from animeverse.application.ports import Rejection, SearchResult, SourceUnavailable
from animeverse.config.franchises import by_relations
from animeverse.domain.models import Anime
from tests.fakes import FakeSource, InMemoryCatalogStore

NARUTO = by_relations("Naruto", search="Naruto", main_anilist_id=900001)
TITAN = by_relations("Attack on Titan", search="Attack on Titan", main_anilist_id=900010)


def naruto_results() -> SearchResult:
    return SearchResult(
        anime=[
            Anime(anilist_id=900001, title="NARUTO", title_english="Naruto"),
            Anime(anilist_id=900002, title="NARUTO: Shippuuden", title_english="Naruto Shippuden"),
            Anime(anilist_id=900003, title="Onigiri", title_english="Onigiri"),  # will be excluded
        ],
        rejected=[Rejection(position=3, source_id=None, reason="'id' is missing")],
        relations={
            900001: frozenset({900002, 800001}),  # 800001: the manga, not a search result
            900002: frozenset({900001}),
            900003: frozenset(),  # Onigiri: unrelated
        },
    )


def titan_results() -> SearchResult:
    return SearchResult(
        anime=[Anime(anilist_id=900010, title="Shingeki no Kyojin")],
        rejected=[],
        relations={900010: frozenset({800010})},
    )


RELATED = {900001: frozenset({900002}), 900002: frozenset({900001})}


def stored_ids(store: InMemoryCatalogStore) -> list[int]:
    return sorted(store.committed.anime)


def test_import_stores_members_and_reports_what_happened():
    store = InMemoryCatalogStore()

    report = ImportCatalog(FakeSource({"Naruto": naruto_results()}), store).import_franchise(NARUTO)

    assert not report.failed
    assert report.fetched == 4
    assert len(report.rejected) == 1
    assert [e.title for e in report.excluded] == ["Onigiri"]
    assert (report.new, report.refreshed, report.new_links) == (2, 0, 2)
    assert stored_ids(store) == [900001, 900002]  # Onigiri was not stored
    assert len(store.committed.links) == 2


def test_importing_twice_creates_nothing_new():
    store = InMemoryCatalogStore()
    use_case = ImportCatalog(FakeSource({"Naruto": naruto_results()}), store)

    use_case.import_franchise(NARUTO)
    second = use_case.import_franchise(NARUTO)

    assert (second.new, second.refreshed, second.new_links) == (0, 2, 0)
    assert stored_ids(store) == [900001, 900002]
    assert len(store.committed.franchises) == 1


def test_source_failure_for_one_franchise_does_not_stop_the_others():
    source = FakeSource({"Naruto": SourceUnavailable("HTTP 503 after 4 attempts"), "Attack on Titan": titan_results()})
    store = InMemoryCatalogStore()

    reports = ImportCatalog(source, store).run([NARUTO, TITAN])

    assert source.queries == ["Naruto", "Attack on Titan"]
    assert reports[0].failed and "HTTP 503" in (reports[0].error or "")
    assert not reports[1].failed and reports[1].new == 1
    assert list(store.committed.franchises) == ["Attack on Titan"]  # nothing written for Naruto


def test_store_failure_undoes_only_that_franchise():
    store = InMemoryCatalogStore()
    source = FakeSource({"Naruto": naruto_results(), "Attack on Titan": titan_results()})
    ImportCatalog(source, store).import_franchise(NARUTO)  # succeeds

    store.fail_after_saves = 0  # the store dies on the next save
    report = ImportCatalog(source, store).import_franchise(TITAN)

    assert report.failed and "store" in (report.error or "")
    assert (report.new, report.refreshed, report.new_links) == (0, 0, 0)
    assert list(store.committed.franchises) == ["Naruto"]  # Attack on Titan was undone
    assert stored_ids(store) == [900001, 900002]


def test_store_unavailable_before_starting_is_reported():
    store = InMemoryCatalogStore()
    store.unavailable = True

    report = ImportCatalog(FakeSource({"Naruto": naruto_results()}), store).import_franchise(NARUTO)

    assert report.failed and "store" in (report.error or "")


def test_refused_anime_does_not_stop_the_franchise():
    bad = Anime(anilist_id=900001, title="NARUTO", episodes=-1)  # the store refuses negative episodes
    good = Anime(anilist_id=900002, title="NARUTO: Shippuuden")
    store = InMemoryCatalogStore()

    source = FakeSource({"Naruto": SearchResult([bad, good], [], RELATED)})

    report = ImportCatalog(source, store).import_franchise(NARUTO)

    assert not report.failed
    assert [u.anilist_id for u in report.unsaved] == [900001]
    assert (report.new, report.refreshed, report.new_links) == (1, 0, 1)
    assert stored_ids(store) == [900002]


def test_undecidable_membership_fails_the_franchise_and_saves_nothing():
    without_main = SearchResult([Anime(anilist_id=900002, title="NARUTO: Shippuuden")], [], RELATED)
    store = InMemoryCatalogStore()

    report = ImportCatalog(FakeSource({"Naruto": without_main}), store).import_franchise(NARUTO)

    assert report.failed and "membership" in (report.error or "")
    assert store.committed.franchises == {} and stored_ids(store) == []
