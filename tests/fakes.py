"""In-memory stand-ins for the ports, used by the unit tests.

InMemoryCatalogStore follows the same contract as the PostgreSQL store:
the contract tests (tests/test_store_contract.py, tests/test_query_contract.py)
run the same checks against both, so tests that use the fake can trust it.
"""

import copy
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from animeverse.application.ports import (
    AnimeFilters,
    CatalogAnime,
    FranchiseCount,
    FranchiseRef,
    Page,
    PageRequest,
    RecordRefused,
    SavedEntry,
    SavedMember,
    SearchResult,
    Sort,
    SortField,
    SourceUnavailable,
    StoredWatchlistEntry,
    StoreUnavailable,
    UnlinkedAnime,
)
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry


class FakeSource:
    """Returns (or raises) what each query was given, and records the queries."""

    def __init__(self, results: dict[str, SearchResult | Exception]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str) -> SearchResult:
        self.queries.append(query)
        result = self.results[query]
        if isinstance(result, Exception):
            raise result
        return result


@dataclass
class _State:
    franchises: dict[str, tuple[int, Franchise]] = field(default_factory=dict)  # name -> (id, franchise)
    anime: dict[int, Anime] = field(default_factory=dict)  # anilist_id -> anime
    links: set[tuple[int, int]] = field(default_factory=set)  # (franchise_id, anilist_id)
    ids: dict[int, int] = field(default_factory=dict)  # anilist_id -> AnimeVerse id (like anime.id)
    refreshed_at: dict[int, datetime] = field(default_factory=dict)  # anilist_id -> last import
    watchlist: dict[int, StoredWatchlistEntry] = field(default_factory=dict)  # anime id -> entry
    last_id: int = 0  # the last AnimeVerse id given out


class InMemoryCatalogStore:
    """Every storage port (CatalogStore, CatalogQuery, WatchlistStore) kept in dicts.

    Sessions have real commit/rollback behaviour.
    """

    def __init__(self) -> None:
        self.committed = _State()
        self.unavailable = False  # set to True to simulate a store that is down
        self.fail_after_saves: int | None = None  # simulate the store dying in the middle of a session
        self.fail_on_keep_only_links = False  # simulate the store dying while reconciling links

    @contextmanager
    def session(self) -> Iterator["_InMemorySession"]:
        if self.unavailable:
            raise StoreUnavailable("in-memory store is down")
        session = _InMemorySession(copy.deepcopy(self.committed), self.fail_after_saves, self.fail_on_keep_only_links)
        yield session  # if the block raises, the working copy is simply dropped (rollback)
        self.committed = session.state  # commit

    # --- Test helpers ---------------------------------------------------------------

    def anime_id_of(self, anilist_id: int) -> int:
        """The AnimeVerse id given to an anime when it was first saved."""
        return self.committed.ids[anilist_id]

    def _check_available(self) -> None:
        if self.unavailable:
            raise StoreUnavailable("in-memory store is down")

    # --- CatalogQuery ---------------------------------------------------------------

    def list_anime(self, filters: AnimeFilters, sort: Sort, page: PageRequest) -> Page[CatalogAnime]:
        self._check_available()
        matches = [a for a in self._all_catalog_anime() if _matches(a, filters)]
        ordered = _sorted(matches, sort)
        return Page(ordered[page.offset : page.offset + page.size], len(matches), page)

    def get_anime(self, anime_id: int) -> CatalogAnime | None:
        self._check_available()
        return next((a for a in self._all_catalog_anime() if a.id == anime_id), None)

    def list_franchises(self) -> list[FranchiseCount]:
        self._check_available()
        return [
            FranchiseCount(franchise_id, name, sum(1 for f, _ in self.committed.links if f == franchise_id))
            for name, (franchise_id, _) in sorted(self.committed.franchises.items())
        ]

    def _all_catalog_anime(self) -> list[CatalogAnime]:
        state = self.committed
        names = {franchise_id: name for name, (franchise_id, _) in state.franchises.items()}
        result = []
        for anilist_id, anime in state.anime.items():
            anime_id = state.ids[anilist_id]
            franchises = sorted(
                (FranchiseRef(f, names[f]) for f, a in state.links if a == anilist_id), key=lambda r: r.name
            )
            result.append(
                CatalogAnime(
                    id=anime_id,
                    anime=anime,
                    franchises=tuple(franchises),
                    watchlist_entry=state.watchlist.get(anime_id),
                    updated_at=state.refreshed_at[anilist_id],
                )
            )
        return result

    # --- WatchlistStore -------------------------------------------------------------

    def save(self, anime_id: int, entry: WatchlistEntry) -> SavedEntry:
        self._check_available()
        if anime_id not in self.committed.ids.values():
            raise RecordRefused(f"anime {anime_id} does not exist")  # PostgreSQL: foreign key
        _refuse_what_postgres_refuses_in_the_watchlist(entry)
        now = datetime.now(UTC)
        previous = self.committed.watchlist.get(anime_id)
        stored = StoredWatchlistEntry(anime_id, entry, previous.created_at if previous else now, now)
        self.committed.watchlist[anime_id] = stored
        return SavedEntry(stored, created=previous is None)

    def delete(self, anime_id: int) -> bool:
        self._check_available()
        return self.committed.watchlist.pop(anime_id, None) is not None


class _InMemorySession:
    def __init__(self, state: _State, fail_after_saves: int | None, fail_on_keep_only_links: bool = False) -> None:
        self.state = state
        self._saves_left = fail_after_saves
        self._fail_on_keep_only_links = fail_on_keep_only_links

    def save_franchise(self, franchise: Franchise) -> int:
        existing = self.state.franchises.get(franchise.name)
        franchise_id = existing[0] if existing else len(self.state.franchises) + 1
        self.state.franchises[franchise.name] = (franchise_id, franchise)
        return franchise_id

    def save_member(self, franchise_id: int, anime: Anime) -> SavedMember:
        if self._saves_left is not None:
            if self._saves_left == 0:
                raise StoreUnavailable("in-memory store died")
            self._saves_left -= 1
        _refuse_what_postgres_refuses(anime)
        created = anime.anilist_id not in self.state.anime
        self.state.anime[anime.anilist_id] = anime
        if anime.anilist_id not in self.state.ids:  # like a PostgreSQL sequence: an id is never reused
            self.state.last_id += 1
            self.state.ids[anime.anilist_id] = self.state.last_id
        self.state.refreshed_at[anime.anilist_id] = datetime.now(UTC)
        link = (franchise_id, anime.anilist_id)
        newly_linked = link not in self.state.links
        self.state.links.add(link)
        return SavedMember(created=created, newly_linked=newly_linked)

    def keep_only_links(self, franchise_id: int, anilist_ids: frozenset[int]) -> list[UnlinkedAnime]:
        if self._fail_on_keep_only_links:
            raise StoreUnavailable("in-memory store died")
        removed = sorted(a for f, a in self.state.links if f == franchise_id and a not in anilist_ids)
        self.state.links -= {(franchise_id, a) for a in removed}
        unlinked = []
        for anilist_id in removed:
            title = self.state.anime[anilist_id].title
            still_linked = any(a == anilist_id for _, a in self.state.links)
            in_watchlist = self.state.ids[anilist_id] in self.state.watchlist
            deleted = not still_linked and not in_watchlist
            if deleted:  # like PostgreSQL's DELETE: the anime and everything kept about it
                del self.state.anime[anilist_id], self.state.ids[anilist_id], self.state.refreshed_at[anilist_id]
            unlinked.append(UnlinkedAnime(anilist_id, title, deleted))
        return unlinked


def _refuse_what_postgres_refuses(anime: Anime) -> None:
    """The CHECK constraints of the anime table, so the fake refuses the same records."""
    problems = [
        (anime.episodes is not None and anime.episodes < 0, "episodes must be >= 0"),
        (anime.popularity is not None and anime.popularity < 0, "popularity must be >= 0"),
        (anime.score is not None and not Decimal(0) <= anime.score <= Decimal(10), "score must be 0-10"),
        (anime.start_year is not None and anime.start_year <= 0, "start_year must be > 0"),
        (anime.end_year is not None and anime.end_year <= 0, "end_year must be > 0"),
        (not anime.title, "title is required"),
    ]
    for broken, message in problems:
        if broken:
            raise RecordRefused(message)


def _refuse_what_postgres_refuses_in_the_watchlist(entry: WatchlistEntry) -> None:
    """The CHECK constraints of the watchlist_entries table (migration 0002)."""
    problems = [
        (entry.episodes_watched < 0, "episodes_watched must be >= 0"),
        (entry.rating is not None and not 1 <= entry.rating <= 10, "rating must be 1-10"),
        (entry.notes is not None and len(entry.notes) > 1000, "notes must be at most 1000 characters"),
        (entry.notes is not None and not entry.notes.strip(), "notes must not be blank"),
    ]
    for broken, message in problems:
        if broken:
            raise RecordRefused(message)


# --- Filtering and sorting, as the PostgreSQL queries do it -------------------------------


def _matches(item: CatalogAnime, f: AnimeFilters) -> bool:
    anime, entry = item.anime, item.watchlist_entry
    checks = [
        f.text is None
        or any(
            f.text.casefold() in t.casefold() for t in (anime.title, anime.title_english, anime.title_japanese) if t
        ),
        f.franchise_id is None or any(r.id == f.franchise_id for r in item.franchises),
        f.status is None or anime.status == f.status,
        f.format is None or anime.type == f.format,
        f.year_from is None or (anime.start_year is not None and anime.start_year >= f.year_from),
        f.year_to is None or (anime.start_year is not None and anime.start_year <= f.year_to),
        f.min_score is None or (anime.score is not None and anime.score >= f.min_score),
        f.on_watchlist is None or (entry is not None) == f.on_watchlist,
        f.watchlist_status is None or (entry is not None and entry.entry.status == f.watchlist_status),
    ]
    return all(checks)


_SORT_KEYS: dict[SortField, Callable[[Anime], Any]] = {
    SortField.POPULARITY: lambda a: a.popularity,
    SortField.SCORE: lambda a: a.score,
    SortField.START_YEAR: lambda a: a.start_year,
    SortField.TITLE: lambda a: a.title.casefold(),
}


def _sorted(items: list[CatalogAnime], sort: Sort) -> list[CatalogAnime]:
    """Missing values last, in either direction; ties by id ascending."""
    key = _SORT_KEYS[sort.field]
    by_id = sorted(items, key=lambda a: a.id)
    with_value = [a for a in by_id if key(a.anime) is not None]
    without_value = [a for a in by_id if key(a.anime) is None]
    # sorted() is stable, also with reverse=True: equal values keep their id order.
    return sorted(with_value, key=lambda a: key(a.anime), reverse=sort.descending) + without_value


__all__ = ["FakeSource", "InMemoryCatalogStore", "SourceUnavailable"]
