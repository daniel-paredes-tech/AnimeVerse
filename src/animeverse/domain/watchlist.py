"""The watchlist: the user's own tracking of an anime, and its rules (ADR 0011).

A WatchlistEntry holds data only. check_entry() returns every rule the entry
breaks (not just the first), so a form can show all the problems at once.

Rules:
- single fields: episodes watched 0..MAX_EPISODES_WATCHED, rating 1..10 (or
  none), notes up to MAX_NOTES_LENGTH characters;
- compared with the anime (only when its number of episodes is known):
    exceeds_episodes                 episodes watched > the anime's episodes
    completed_requires_all_episodes  completed, but not every episode watched
- planning_requires_zero_episodes    planning, but episodes already watched

The codes are part of the API contract (openapi.yaml, FieldError.code):
never rename one.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

MAX_EPISODES_WATCHED = 10_000  # a sanity limit; the longest anime stored has 500
MAX_NOTES_LENGTH = 1000
MIN_RATING = 1
MAX_RATING = 10


class WatchStatus(StrEnum):
    PLANNING = "planning"
    WATCHING = "watching"
    COMPLETED = "completed"
    PAUSED = "paused"
    DROPPED = "dropped"


@dataclass(frozen=True)
class WatchlistEntry:
    status: WatchStatus
    episodes_watched: int
    rating: int | None  # None: not rated
    notes: str | None  # None: no notes


@dataclass(frozen=True)
class RuleViolation:
    """One broken rule: which field, a stable machine-readable code, and a message for people."""

    field: str
    code: str
    message: str


def check_entry(entry: WatchlistEntry, total_episodes: int | None) -> list[RuleViolation]:
    """Every rule the entry breaks, in field order. Empty if the entry is valid.

    total_episodes is the anime's number of episodes, or None when unknown
    (e.g. still airing): then any number of watched episodes is accepted.
    """
    return [*_check_episodes(entry, total_episodes), *_check_rating(entry.rating), *_check_notes(entry.notes)]


def without_blank_notes(entry: WatchlistEntry) -> WatchlistEntry:
    """The same entry, with empty or whitespace-only notes turned into None ("no notes").

    Real notes are kept exactly as written, spaces included.
    """
    if entry.notes is not None and not entry.notes.strip():
        return replace(entry, notes=None)
    return entry


def _check_episodes(entry: WatchlistEntry, total: int | None) -> list[RuleViolation]:
    watched = entry.episodes_watched
    if watched < 0:
        return [RuleViolation("episodes_watched", "too_small", "Must be at least 0.")]
    if watched > MAX_EPISODES_WATCHED:
        return [RuleViolation("episodes_watched", "too_large", f"Must be at most {MAX_EPISODES_WATCHED}.")]
    if total is not None and watched > total:
        return [
            RuleViolation("episodes_watched", "exceeds_episodes", f"Can't be more than the anime's {_episodes(total)}.")
        ]
    if entry.status is WatchStatus.COMPLETED and total is not None and watched != total:
        return [
            RuleViolation(
                "episodes_watched",
                "completed_requires_all_episodes",
                f"A completed anime needs all {_episodes(total)} watched.",
            )
        ]
    if entry.status is WatchStatus.PLANNING and watched != 0:
        return [
            RuleViolation(
                "episodes_watched",
                "planning_requires_zero_episodes",
                "An anime you plan to watch can't have episodes watched yet.",
            )
        ]
    return []


def _check_rating(rating: int | None) -> list[RuleViolation]:
    if rating is None:
        return []
    if rating < MIN_RATING:
        return [RuleViolation("rating", "too_small", f"Must be at least {MIN_RATING}.")]
    if rating > MAX_RATING:
        return [RuleViolation("rating", "too_large", f"Must be at most {MAX_RATING}.")]
    return []


def _check_notes(notes: str | None) -> list[RuleViolation]:
    if notes is not None and len(notes) > MAX_NOTES_LENGTH:
        return [RuleViolation("notes", "too_long", f"Must be at most {MAX_NOTES_LENGTH} characters.")]
    return []


def _episodes(count: int) -> str:
    return f"{count} episode" if count == 1 else f"{count} episodes"
