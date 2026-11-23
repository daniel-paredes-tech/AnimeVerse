"""The watchlist rules (domain/watchlist.py): pure functions, no database."""

import pytest

from animeverse.domain.watchlist import (
    MAX_EPISODES_WATCHED,
    MAX_NOTES_LENGTH,
    RuleViolation,
    WatchlistEntry,
    WatchStatus,
    check_entry,
    without_blank_notes,
)


def entry(status=WatchStatus.WATCHING, episodes_watched=0, rating=None, notes=None) -> WatchlistEntry:
    return WatchlistEntry(status=status, episodes_watched=episodes_watched, rating=rating, notes=notes)


def codes(violations: list[RuleViolation]) -> list[tuple[str, str]]:
    return [(v.field, v.code) for v in violations]


# --- Valid entries ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "total_episodes"),
    [
        pytest.param(entry(WatchStatus.WATCHING, 12, rating=8, notes="Great."), 24, id="watching halfway"),
        pytest.param(entry(WatchStatus.COMPLETED, 24, rating=10), 24, id="completed with every episode"),
        pytest.param(entry(WatchStatus.PLANNING, 0), 24, id="planning, nothing watched"),
        pytest.param(entry(WatchStatus.DROPPED, 3, rating=1), 24, id="dropped early, lowest rating"),
        pytest.param(entry(WatchStatus.PAUSED, 24), 24, id="paused on the last episode"),
        pytest.param(entry(WatchStatus.WATCHING, 600), None, id="unknown total: any count is fine"),
        pytest.param(entry(WatchStatus.COMPLETED, 5), None, id="completed, unknown total"),
        pytest.param(entry(notes="x" * MAX_NOTES_LENGTH), 24, id="longest notes"),
        pytest.param(entry(episodes_watched=MAX_EPISODES_WATCHED), None, id="most episodes"),
    ],
)
def test_valid_entries_have_no_violations(candidate, total_episodes):
    assert check_entry(candidate, total_episodes) == []


# --- Single-field limits --------------------------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        pytest.param(entry(episodes_watched=-1), ("episodes_watched", "too_small"), id="negative episodes"),
        pytest.param(
            entry(episodes_watched=MAX_EPISODES_WATCHED + 1), ("episodes_watched", "too_large"), id="too many episodes"
        ),
        pytest.param(entry(rating=0), ("rating", "too_small"), id="rating 0"),
        pytest.param(entry(rating=11), ("rating", "too_large"), id="rating 11"),
        pytest.param(entry(notes="x" * (MAX_NOTES_LENGTH + 1)), ("notes", "too_long"), id="notes too long"),
    ],
)
def test_single_field_limits(candidate, expected):
    assert codes(check_entry(candidate, None)) == [expected]


# --- Rules that compare the entry with its anime --------------------------------------


def test_episodes_watched_cannot_exceed_the_anime():
    violations = check_entry(entry(WatchStatus.WATCHING, 25), total_episodes=24)

    assert codes(violations) == [("episodes_watched", "exceeds_episodes")]
    assert violations[0].message == "Can't be more than the anime's 24 episodes."


def test_the_message_uses_the_singular_for_one_episode():
    violations = check_entry(entry(WatchStatus.WATCHING, 2), total_episodes=1)

    assert violations[0].message == "Can't be more than the anime's 1 episode."


def test_completed_needs_every_episode():
    violations = check_entry(entry(WatchStatus.COMPLETED, 20), total_episodes=24)

    assert codes(violations) == [("episodes_watched", "completed_requires_all_episodes")]
    assert violations[0].message == "A completed anime needs all 24 episodes watched."


def test_too_many_episodes_on_a_completed_entry_is_reported_once():
    # 30 of 24 breaks "exceeds_episodes"; saying "completed needs 24" as well would add nothing.
    assert codes(check_entry(entry(WatchStatus.COMPLETED, 30), 24)) == [("episodes_watched", "exceeds_episodes")]


def test_planning_means_nothing_watched_yet():
    violations = check_entry(entry(WatchStatus.PLANNING, 1), total_episodes=24)

    assert codes(violations) == [("episodes_watched", "planning_requires_zero_episodes")]


def test_every_broken_rule_is_reported_at_once():
    # The form can then show every problem in one go instead of one per attempt.
    violations = check_entry(entry(WatchStatus.WATCHING, 30, rating=11, notes="x" * 1001), 24)

    assert codes(violations) == [
        ("episodes_watched", "exceeds_episodes"),
        ("rating", "too_large"),
        ("notes", "too_long"),
    ]


# --- Blank notes ----------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_blank_notes_become_none(blank):
    assert without_blank_notes(entry(notes=blank)).notes is None


def test_real_notes_are_kept_exactly():
    assert without_blank_notes(entry(notes="  Rewatch ep 5 ")).notes == "  Rewatch ep 5 "


def test_statuses_are_the_lowercase_api_values():
    assert [s.value for s in WatchStatus] == ["planning", "watching", "completed", "paused", "dropped"]
