"""Ports: the contracts between the use cases and the outside world.

A port says what the application needs, not how it is done. Infrastructure
provides the implementations (adapters): AniList for AnimeSource, PostgreSQL
for CatalogStore, CatalogQuery and WatchlistStore. Tests use
in-memory ones.

Every port lists the errors it may raise. Adapters translate their own
errors (httpx, psycopg...) into these, so no library error crosses a boundary.
"""

import math
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Generic, Protocol, TypeVar

from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus

# --- Errors ---------------------------------------------------------------------


class SourceUnavailable(Exception):
    """The data source could not answer (down, too slow, refused, malformed reply)."""


class RecordRefused(Exception):
    """The store refused one record (a value it cannot store, a broken rule).

    Only that record is undone; the session stays usable for the others.
    """


class StoreUnavailable(Exception):
    """The store failed as a whole (unreachable, connection lost...)."""


# --- Data source ----------------------------------------------------------------------


@dataclass(frozen=True)
class Rejection:
    """A search result that could not become an Anime."""

    position: int  # index of the item in the source's results
    source_id: int | None  # the source's id for the item, when it had a valid one
    reason: str


@dataclass(frozen=True)
class SearchResult:
    anime: list[Anime]  # valid results, in the source's order
    rejected: list[Rejection]  # malformed results; never stop the others
    # Source id of each valid result -> source ids of the media it relates to (sequels,
    # spin-offs, its manga...). Used to decide franchise membership; never stored.
    relations: Mapping[int, frozenset[int]] = field(default_factory=dict)
    # Source ids whose relations came missing, malformed or cut short: their entry in
    # `relations` may lack some ids. An empty list that came complete is not here.
    incomplete_relations: frozenset[int] = frozenset()

    @property
    def fetched(self) -> int:
        return len(self.anime) + len(self.rejected)


class AnimeSource(Protocol):
    def search(self, query: str) -> SearchResult:
        """Every anime matching the query. Raises SourceUnavailable."""
        ...


# --- Storage ----------------------------------------------------------------------------


@dataclass(frozen=True)
class SavedMember:
    created: bool  # True: the anime is new; False: an existing one was refreshed
    newly_linked: bool  # True: the anime was not yet linked to this franchise


@dataclass(frozen=True)
class UnlinkedAnime:
    """An anime removed from a franchise because it no longer belongs to it."""

    anilist_id: int
    title: str
    deleted: bool  # True: it was in no other franchise and not in the watchlist, so it was deleted


class CatalogSession(Protocol):
    """One unit of work. Opened with CatalogStore.session()."""

    def save_franchise(self, franchise: Franchise) -> int:
        """Insert or refresh a franchise (keyed by name). Returns its id."""
        ...

    def save_member(self, franchise_id: int, anime: Anime) -> SavedMember:
        """Insert or refresh an anime (keyed by anilist_id) and link it to the franchise.

        Both happen or neither does. Raises RecordRefused for this anime only.
        """
        ...

    def keep_only_links(self, franchise_id: int, anilist_ids: frozenset[int]) -> list[UnlinkedAnime]:
        """Unlink from the franchise every anime whose AniList id is not in anilist_ids.

        An anime this leaves with no franchise and no watchlist entry is deleted.
        Returns the unlinked anime, ordered by AniList id. Raises StoreUnavailable.
        """
        ...


class CatalogStore(Protocol):
    def session(self) -> AbstractContextManager[CatalogSession]:
        """A unit of work: committed when the block ends normally, undone if it raises.

        Raises StoreUnavailable if the store cannot be used.
        """
        ...


# --- Browsing the catalogue -------------------------------------------------------------


@dataclass(frozen=True)
class FranchiseRef:
    id: int
    name: str


@dataclass(frozen=True)
class FranchiseCount:
    id: int
    name: str
    anime_count: int


@dataclass(frozen=True)
class StoredWatchlistEntry:
    anime_id: int
    entry: WatchlistEntry
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CatalogAnime:
    """A stored anime as the catalogue shows it: with its id, franchises and watchlist entry."""

    id: int  # AnimeVerse's id (anime.id), not AniList's
    anime: Anime
    franchises: tuple[FranchiseRef, ...]  # alphabetical
    watchlist_entry: StoredWatchlistEntry | None
    updated_at: datetime  # when an import last refreshed it


@dataclass(frozen=True)
class AnimeFilters:
    """Every filter is optional; the ones given are combined with AND."""

    text: str | None = None  # contained in any title, ignoring case
    franchise_id: int | None = None
    status: str | None = None  # anime.status, exact
    format: str | None = None  # anime.type, exact
    year_from: int | None = None  # start_year >= (anime without start_year are left out)
    year_to: int | None = None  # start_year <=
    min_score: Decimal | None = None  # score >= (anime without score are left out)
    on_watchlist: bool | None = None
    watchlist_status: WatchStatus | None = None


class SortField(StrEnum):
    POPULARITY = "popularity"
    SCORE = "score"
    START_YEAR = "start_year"
    TITLE = "title"  # ignoring case


@dataclass(frozen=True)
class Sort:
    """Missing values always come last; ties are broken by id (ascending), so pages never overlap."""

    field: SortField = SortField.POPULARITY
    descending: bool = True


@dataclass(frozen=True)
class PageRequest:
    number: int = 1  # starts at 1
    size: int = 24

    @property
    def offset(self) -> int:
        return (self.number - 1) * self.size


T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total_items: int  # matching items over all pages
    request: PageRequest

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total_items / self.request.size)


class CatalogQuery(Protocol):
    """Read-only access to the stored catalogue. Every method raises StoreUnavailable."""

    def list_anime(self, filters: AnimeFilters, sort: Sort, page: PageRequest) -> Page[CatalogAnime]:
        """One page of the anime matching every filter, in the given order.

        A page past the last one is empty (not an error); total_items still counts every match.
        """
        ...

    def get_anime(self, anime_id: int) -> CatalogAnime | None:
        """The anime with this id, or None if there is none."""
        ...

    def list_franchises(self) -> list[FranchiseCount]:
        """Every franchise, alphabetical, with its number of anime (0 included)."""
        ...


# --- The watchlist ----------------------------------------------------------------------


@dataclass(frozen=True)
class SavedEntry:
    stored: StoredWatchlistEntry
    created: bool  # True: new entry; False: an existing one was replaced


class WatchlistStore(Protocol):
    """Writes the user's watchlist. Every method raises StoreUnavailable.

    It trusts its caller: entries are checked against the domain rules before they get here.
    """

    def save(self, anime_id: int, entry: WatchlistEntry) -> SavedEntry:
        """Create or replace the entry of this anime (the anime must exist).

        Raises RecordRefused if the store refuses the values.
        """
        ...

    def delete(self, anime_id: int) -> bool:
        """Remove the entry of this anime. False if there was none."""
        ...


__all__ = [
    "AnimeFilters",
    "AnimeSource",
    "CatalogAnime",
    "CatalogQuery",
    "CatalogSession",
    "CatalogStore",
    "FranchiseCount",
    "FranchiseRef",
    "Page",
    "PageRequest",
    "RecordRefused",
    "Rejection",
    "SavedEntry",
    "SavedMember",
    "SearchResult",
    "Sort",
    "SortField",
    "SourceUnavailable",
    "StoreUnavailable",
    "StoredWatchlistEntry",
    "WatchlistStore",
]
