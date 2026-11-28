"""Tests for the import use case, with in-memory fakes: no network, no database.

All anime below are made-up test data.
"""

from animeverse.application.import_catalog import ImportCatalog
from animeverse.application.ports import Rejection, SearchResult, SourceUnavailable, UnlinkedAnime
from animeverse.config.franchises import by_relations
from animeverse.domain.models import Anime
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
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


# --- Reconciliation: a franchise keeps only its current members ---------------------

MAIN = Anime(anilist_id=900001, title="NARUTO")
SEQUEL = Anime(anilist_id=900002, title="NARUTO: Shippuuden")
MOVIE = Anime(anilist_id=900003, title="NARUTO the Movie")


def naruto(anime: list[Anime], relations: dict[int, frozenset[int]], rejected=None) -> SearchResult:
    return SearchResult(anime, rejected or [], relations)


ALL_RELATED = naruto(
    [MAIN, SEQUEL, MOVIE], {900001: frozenset({900002, 900003}), 900002: frozenset(), 900003: frozenset()}
)
SEQUEL_UNRELATED = naruto(
    [MAIN, SEQUEL, MOVIE], {900001: frozenset({900003}), 900002: frozenset(), 900003: frozenset()}
)


def import_twice(first: SearchResult, second: SearchResult | Exception, store: InMemoryCatalogStore):
    """Import Naruto from `first`, then again from `second`. Returns the second report."""
    ImportCatalog(FakeSource({"Naruto": first}), store).import_franchise(NARUTO)
    return ImportCatalog(FakeSource({"Naruto": second}), store).import_franchise(NARUTO)


def test_an_anime_no_longer_related_is_unlinked_and_deleted():
    store = InMemoryCatalogStore()

    report = import_twice(ALL_RELATED, SEQUEL_UNRELATED, store)

    assert not report.failed and report.reconciliation_skipped is None
    assert report.unlinked == [UnlinkedAnime(900002, "NARUTO: Shippuuden", deleted=True)]
    assert [e.anilist_id for e in report.excluded] == [900002]
    assert stored_ids(store) == [900001, 900003]


def test_an_unlinked_anime_in_the_watchlist_is_kept():
    store = InMemoryCatalogStore()
    ImportCatalog(FakeSource({"Naruto": ALL_RELATED}), store).import_franchise(NARUTO)
    store.save(store.anime_id_of(900002), WatchlistEntry(WatchStatus("watching"), 3, None, None))

    report = ImportCatalog(FakeSource({"Naruto": SEQUEL_UNRELATED}), store).import_franchise(NARUTO)

    assert report.unlinked == [UnlinkedAnime(900002, "NARUTO: Shippuuden", deleted=False)]
    assert stored_ids(store) == [900001, 900002, 900003]
    assert store.anime_id_of(900002) in store.committed.watchlist


def test_rejected_and_refused_anime_keep_their_links():
    store = InMemoryCatalogStore()
    refused_movie = Anime(anilist_id=900003, title="NARUTO the Movie", episodes=-1)  # the store refuses it
    second = naruto(
        [MAIN, refused_movie],
        {900001: frozenset({900003}), 900003: frozenset()},
        rejected=[Rejection(position=1, source_id=900002, reason="'title' must be an object")],
    )

    report = import_twice(ALL_RELATED, second, store)

    assert not report.failed and report.unlinked == []
    assert stored_ids(store) == [900001, 900002, 900003]
    assert len(store.committed.links) == 3


def test_a_rejection_without_id_skips_reconciliation():
    store = InMemoryCatalogStore()
    second = naruto(
        SEQUEL_UNRELATED.anime,
        dict(SEQUEL_UNRELATED.relations),
        rejected=[Rejection(position=3, source_id=None, reason="'id' is missing")],
    )

    report = import_twice(ALL_RELATED, second, store)

    assert not report.failed
    assert report.reconciliation_skipped is not None and "without an id" in report.reconciliation_skipped
    assert report.unlinked == []
    assert stored_ids(store) == [900001, 900002, 900003] and len(store.committed.links) == 3


def test_undecidable_membership_touches_nothing():
    store = InMemoryCatalogStore()
    no_relations = naruto([MAIN, SEQUEL, MOVIE], {900001: frozenset(), 900002: frozenset(), 900003: frozenset()})

    report = import_twice(ALL_RELATED, no_relations, store)

    assert report.failed and "membership" in (report.error or "")
    assert stored_ids(store) == [900001, 900002, 900003] and len(store.committed.links) == 3


def test_source_failure_touches_nothing():
    store = InMemoryCatalogStore()

    report = import_twice(ALL_RELATED, SourceUnavailable("HTTP 503"), store)

    assert report.failed and report.unlinked == []
    assert stored_ids(store) == [900001, 900002, 900003] and len(store.committed.links) == 3


def test_store_failure_during_reconciliation_undoes_the_franchise():
    store = InMemoryCatalogStore()
    ImportCatalog(FakeSource({"Naruto": ALL_RELATED}), store).import_franchise(NARUTO)
    new_ova = Anime(anilist_id=900004, title="NARUTO OVA")
    second = naruto(
        [MAIN, SEQUEL, MOVIE, new_ova],
        {900001: frozenset({900003, 900004}), 900002: frozenset(), 900003: frozenset(), 900004: frozenset()},
    )

    store.fail_on_keep_only_links = True
    report = ImportCatalog(FakeSource({"Naruto": second}), store).import_franchise(NARUTO)

    assert report.failed and "store" in (report.error or "")
    assert stored_ids(store) == [900001, 900002, 900003]  # the new OVA was undone too
    assert len(store.committed.links) == 3
