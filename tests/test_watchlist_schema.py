"""The database's own rules for watchlist_entries (migration 0002, ADR 0011).

These are the last line of defence: the domain validates an entry before it
gets here, but the table must refuse impossible values even if a bug (or a
manual INSERT) skips the domain. The rules that compare a field with the
anime (episodes watched vs total episodes) are the domain's, not tested here.
"""

import psycopg
import pytest

from animeverse.domain.models import Anime
from animeverse.infrastructure.postgres.repository import upsert_anime

INSERT = "INSERT INTO watchlist_entries (anime_id, status, episodes_watched, rating, notes) VALUES (%s, %s, %s, %s, %s)"


@pytest.fixture
def anime_id(conn):
    """The id of a made-up anime to attach entries to."""
    return upsert_anime(conn, Anime(anilist_id=900001, title="Test Anime", episodes=24)).id


def test_a_valid_entry_is_stored_with_timestamps(conn, anime_id):
    conn.execute(INSERT, (anime_id, "watching", 3, 8, "Good so far."))

    row = conn.execute(
        "SELECT status, episodes_watched, rating, notes, created_at IS NOT NULL, updated_at IS NOT NULL"
        " FROM watchlist_entries WHERE anime_id = %s",
        (anime_id,),
    ).fetchone()
    assert row == ("watching", 3, 8, "Good so far.", True, True)


def test_rating_and_notes_are_optional_and_episodes_default_to_zero(conn, anime_id):
    conn.execute("INSERT INTO watchlist_entries (anime_id, status) VALUES (%s, 'planning')", (anime_id,))

    row = conn.execute("SELECT episodes_watched, rating, notes FROM watchlist_entries").fetchone()
    assert row == (0, None, None)


@pytest.mark.parametrize("status", ["planning", "watching", "completed", "paused", "dropped"])
def test_every_watch_status_is_accepted(conn, anime_id, status):
    conn.execute(INSERT, (anime_id, status, 0, None, None))


def test_one_entry_per_anime(conn, anime_id):
    conn.execute(INSERT, (anime_id, "watching", 1, None, None))

    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(INSERT, (anime_id, "completed", 24, None, None))


def test_an_entry_needs_an_existing_anime(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        conn.execute(INSERT, (999_999, "watching", 0, None, None))


@pytest.mark.parametrize(
    ("status", "episodes_watched", "rating", "notes"),
    [
        pytest.param("WATCHING", 0, None, None, id="status is case-sensitive"),
        pytest.param("finished", 0, None, None, id="unknown status"),
        pytest.param("watching", -1, None, None, id="negative episodes"),
        pytest.param("watching", 0, 0, None, id="rating below 1"),
        pytest.param("watching", 0, 11, None, id="rating above 10"),
        pytest.param("watching", 0, None, "x" * 1001, id="notes too long"),
        pytest.param("watching", 0, None, "", id="empty notes (use NULL)"),
        pytest.param("watching", 0, None, "   ", id="blank notes (use NULL)"),
    ],
)
def test_impossible_values_are_refused(conn, anime_id, status, episodes_watched, rating, notes):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(INSERT, (anime_id, status, episodes_watched, rating, notes))


def test_notes_of_exactly_1000_characters_are_accepted(conn, anime_id):
    conn.execute(INSERT, (anime_id, "watching", 0, None, "x" * 1000))


def test_status_and_episodes_watched_cannot_be_null(conn, anime_id):
    with pytest.raises(psycopg.errors.NotNullViolation):
        conn.execute(INSERT, (anime_id, None, 0, None, None))


def test_deleting_an_anime_deletes_its_entry(conn, anime_id, count_rows):
    conn.execute(INSERT, (anime_id, "watching", 0, None, None))

    conn.execute("DELETE FROM anime WHERE id = %s", (anime_id,))

    assert count_rows("watchlist_entries") == 0
