"""In-memory stand-ins for the ports, used by the unit tests.

InMemoryCatalogStore follows the same contract as the PostgreSQL store:
the contract tests in tests/test_store_contract.py run the same checks
against both, so tests that use the fake can trust it.
"""

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from animeverse.application.ports import (
    RecordRefused,
    SavedMember,
    SearchResult,
    SourceUnavailable,
    StoreUnavailable,
)
from animeverse.domain.models import Anime, Franchise


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


class InMemoryCatalogStore:
    """CatalogStore and CatalogReader kept in a dict, with real commit/rollback behaviour."""

    def __init__(self) -> None:
        self.committed = _State()
        self.unavailable = False  # set to True to simulate a store that is down
        self.fail_after_saves: int | None = None  # simulate the store dying in the middle of a session

    @contextmanager
    def session(self) -> Iterator["_InMemorySession"]:
        if self.unavailable:
            raise StoreUnavailable("in-memory store is down")
        session = _InMemorySession(copy.deepcopy(self.committed), self.fail_after_saves)
        yield session  # if the block raises, the working copy is simply dropped (rollback)
        self.committed = session.state  # commit

    def anime_by_franchise(self) -> dict[str, list[Anime]]:
        if self.unavailable:
            raise StoreUnavailable("in-memory store is down")
        result: dict[str, list[Anime]] = {}
        for name, (franchise_id, _) in sorted(self.committed.franchises.items()):
            members = [self.committed.anime[a] for f, a in self.committed.links if f == franchise_id]
            members.sort(key=lambda a: (a.popularity is None, -(a.popularity or 0), a.title))
            result[name] = members
        return result


class _InMemorySession:
    def __init__(self, state: _State, fail_after_saves: int | None) -> None:
        self.state = state
        self._saves_left = fail_after_saves

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
        link = (franchise_id, anime.anilist_id)
        newly_linked = link not in self.state.links
        self.state.links.add(link)
        return SavedMember(created=created, newly_linked=newly_linked)


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


__all__ = ["FakeSource", "InMemoryCatalogStore", "SourceUnavailable"]
