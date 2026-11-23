"""Use case: browse the stored catalogue (list with filters, get one, franchises).

Mostly a thin layer over the CatalogQuery port, which does the real work.
What it adds is the application's own rules, so that every entrypoint (the
API today, maybe a CLI later) gets the same answers:
- a query that can't be answered is refused before reaching the store
  (InvalidQuery: year_from after year_to, page or page size out of range);
- a missing anime is an error (AnimeNotFound), not a None to check everywhere.
"""

from animeverse.application.errors import AnimeNotFound, InvalidQuery
from animeverse.application.ports import (
    AnimeFilters,
    CatalogAnime,
    CatalogQuery,
    FranchiseCount,
    Page,
    PageRequest,
    Sort,
)
from animeverse.domain.watchlist import RuleViolation

MAX_PAGE_SIZE = 100


class BrowseCatalog:
    def __init__(self, query: CatalogQuery) -> None:
        self._query = query

    def list_anime(self, filters: AnimeFilters, sort: Sort, page: PageRequest) -> Page[CatalogAnime]:
        """Raises InvalidQuery or StoreUnavailable."""
        violations = _check_query(filters, page)
        if violations:
            raise InvalidQuery(violations)
        return self._query.list_anime(filters, sort, page)

    def get_anime(self, anime_id: int) -> CatalogAnime:
        """Raises AnimeNotFound or StoreUnavailable."""
        anime = self._query.get_anime(anime_id)
        if anime is None:
            raise AnimeNotFound(anime_id)
        return anime

    def list_franchises(self) -> list[FranchiseCount]:
        """Raises StoreUnavailable."""
        return self._query.list_franchises()


def _check_query(filters: AnimeFilters, page: PageRequest) -> list[RuleViolation]:
    violations = []
    if filters.year_from is not None and filters.year_to is not None and filters.year_to < filters.year_from:
        violations.append(
            RuleViolation("year_to", "too_small", f"Must not be less than year_from ({filters.year_from}).")
        )
    if page.number < 1:
        violations.append(RuleViolation("page", "too_small", "Must be at least 1."))
    if page.size < 1:
        violations.append(RuleViolation("page_size", "too_small", "Must be at least 1."))
    elif page.size > MAX_PAGE_SIZE:
        violations.append(RuleViolation("page_size", "too_large", f"Must be at most {MAX_PAGE_SIZE}."))
    return violations
