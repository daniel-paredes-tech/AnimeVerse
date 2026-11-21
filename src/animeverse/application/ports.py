"""Ports: the contracts between the use cases and the outside world.

A port says what the application needs, not how it is done. Infrastructure
provides the implementations (adapters): AniList for AnimeSource, PostgreSQL
for CatalogStore and CatalogReader. Tests use in-memory ones.

Every port lists the errors it may raise. Adapters translate their own
errors (httpx, psycopg...) into these, so no library error crosses a boundary.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from animeverse.domain.models import Anime, Franchise

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


class CatalogStore(Protocol):
    def session(self) -> AbstractContextManager[CatalogSession]:
        """A unit of work: committed when the block ends normally, undone if it raises.

        Raises StoreUnavailable if the store cannot be used.
        """
        ...


class CatalogReader(Protocol):
    def anime_by_franchise(self) -> dict[str, list[Anime]]:
        """Every franchise (alphabetical) with its anime (most popular first).

        Franchises without anime are included with an empty list.
        Raises StoreUnavailable.
        """
        ...


__all__ = [
    "AnimeSource",
    "CatalogReader",
    "CatalogSession",
    "CatalogStore",
    "RecordRefused",
    "Rejection",
    "SavedMember",
    "SearchResult",
    "SourceUnavailable",
    "StoreUnavailable",
]
