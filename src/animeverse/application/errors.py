"""Errors the use cases raise, so entrypoints can answer them (the API maps them to HTTP).

    NotFound                  -> 404
        AnimeNotFound
        WatchlistEntryNotFound
    InvalidInput              -> 400 (InvalidQuery) or 422 (InvalidWatchlistEntry)

The ports' own errors (StoreUnavailable...) are in ports.py.
"""

from animeverse.domain.watchlist import RuleViolation


class NotFound(Exception):
    """Something asked for does not exist. The message says what, for people."""


class AnimeNotFound(NotFound):
    def __init__(self, anime_id: int) -> None:
        super().__init__(f"There is no anime with id {anime_id}.")
        self.anime_id = anime_id


class WatchlistEntryNotFound(NotFound):
    def __init__(self, anime_id: int) -> None:
        super().__init__(f"The anime with id {anime_id} is not on your watchlist.")
        self.anime_id = anime_id


class InvalidInput(Exception):
    """The input breaks one or more rules. Carries every violation, not just the first."""

    def __init__(self, violations: list[RuleViolation]) -> None:
        count = len(violations)
        super().__init__(f"{count} rule{'' if count == 1 else 's'} broken")
        self.violations = violations


class InvalidQuery(InvalidInput):
    """A query (filters, page) that can't be answered, e.g. year_from after year_to."""


class InvalidWatchlistEntry(InvalidInput):
    """A watchlist entry that breaks the domain rules (domain/watchlist.py)."""
