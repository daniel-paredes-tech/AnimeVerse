"""Tests for animeverse.repository against a real PostgreSQL test database.

All anime below are made-up test data, not real AniList responses.
"""

import dataclasses
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from animeverse.models import Anime, Franchise
from animeverse.repository import link_anime_to_franchise, upsert_anime, upsert_franchise

FULL_ANIME = Anime(
    anilist_id=900001,
    title="Test Anime",
    mal_id=800001,
    title_english="Test Anime (English)",
    title_japanese="テストアニメ",
    type="TV",
    episodes=24,
    status="FINISHED",
    aired_from=date(2020, 4, 1),
    aired_to=date(2020, 9, 30),
    score=Decimal("8.50"),
    popularity=123456,
    synopsis="A made-up anime used only in tests.",
    image_url="https://example.com/test.jpg",
    anilist_url="https://example.com/anime/900001",
)


# --- Franchises -------------------------------------------------------------


def test_upsert_franchise_inserts_and_returns_id(conn, count_rows):
    franchise_id = upsert_franchise(conn, Franchise("Test Franchise", "test"))

    assert isinstance(franchise_id, int)
    assert count_rows("franchises") == 1


def test_upsert_franchise_twice_keeps_one_row_and_updates_query(conn, count_rows):
    first_id = upsert_franchise(conn, Franchise("Test Franchise", "test"))
    second_id = upsert_franchise(conn, Franchise("Test Franchise", "test v2"))

    assert first_id == second_id
    assert count_rows("franchises") == 1
    query = conn.execute("SELECT search_query FROM franchises").fetchone()[0]
    assert query == "test v2"


# --- Anime ------------------------------------------------------------------


def test_upsert_anime_stores_every_field(conn):
    anime_id = upsert_anime(conn, FULL_ANIME)

    row = conn.execute(
        """
        SELECT anilist_id, title, mal_id, title_english, title_japanese, type,
               episodes, status, aired_from, aired_to, score, popularity,
               synopsis, image_url, anilist_url
        FROM anime WHERE id = %s
        """,
        (anime_id,),
    ).fetchone()
    # Reading back must give the same values and Python types we wrote.
    assert Anime(*row) == FULL_ANIME


def test_upsert_anime_with_only_required_fields_stores_nulls(conn):
    anime_id = upsert_anime(conn, Anime(anilist_id=900002, title="Minimal Anime"))

    row = conn.execute(
        "SELECT mal_id, episodes, score, aired_from FROM anime WHERE id = %s", (anime_id,)
    ).fetchone()
    assert row == (None, None, None, None)


def test_two_anime_may_share_a_mal_id(conn, count_rows):
    # mal_id is untrusted reference data, so it is deliberately not unique.
    upsert_anime(conn, Anime(anilist_id=900003, title="First", mal_id=800003))
    upsert_anime(conn, Anime(anilist_id=900004, title="Second", mal_id=800003))

    assert count_rows("anime") == 2


def test_upsert_anime_twice_keeps_one_row_and_updates_values(conn, count_rows):
    first_id = upsert_anime(conn, FULL_ANIME)
    created_before = conn.execute("SELECT created_at FROM anime WHERE id = %s", (first_id,)).fetchone()[0]

    changed = dataclasses.replace(FULL_ANIME, score=Decimal("9.10"), popularity=200000)
    second_id = upsert_anime(conn, changed)

    assert first_id == second_id
    assert count_rows("anime") == 1
    score, popularity, created_after = conn.execute(
        "SELECT score, popularity, created_at FROM anime WHERE id = %s", (first_id,)
    ).fetchone()
    assert (score, popularity) == (Decimal("9.10"), 200000)
    assert created_after == created_before  # an update must not reset created_at


# --- Links between anime and franchises -------------------------------------


def test_link_twice_creates_one_link(conn, count_rows):
    franchise_id = upsert_franchise(conn, Franchise("Test Franchise", "test"))
    anime_id = upsert_anime(conn, FULL_ANIME)

    assert link_anime_to_franchise(conn, anime_id, franchise_id) is True
    assert link_anime_to_franchise(conn, anime_id, franchise_id) is False
    assert count_rows("anime_franchises") == 1


def test_anime_can_belong_to_two_franchises(conn, count_rows):
    first = upsert_franchise(conn, Franchise("Franchise A", "a"))
    second = upsert_franchise(conn, Franchise("Franchise B", "b"))
    anime_id = upsert_anime(conn, FULL_ANIME)

    link_anime_to_franchise(conn, anime_id, first)
    link_anime_to_franchise(conn, anime_id, second)

    assert count_rows("anime") == 1
    assert count_rows("anime_franchises") == 2


# --- Repeated imports -------------------------------------------------------


def _import_once(conn):
    """Simulate one import run: a franchise, three anime and their links."""
    franchise_id = upsert_franchise(conn, Franchise("Test Franchise", "test"))
    for anilist_id in (900010, 900011, 900012):
        anime_id = upsert_anime(conn, Anime(anilist_id=anilist_id, title=f"Anime {anilist_id}"))
        link_anime_to_franchise(conn, anime_id, franchise_id)


def test_repeated_import_does_not_create_duplicates(conn, count_rows):
    _import_once(conn)
    counts_after_first = (count_rows("franchises"), count_rows("anime"), count_rows("anime_franchises"))

    _import_once(conn)
    counts_after_second = (count_rows("franchises"), count_rows("anime"), count_rows("anime_franchises"))

    assert counts_after_first == (1, 3, 3)
    assert counts_after_second == counts_after_first


# --- The database refuses invalid data --------------------------------------


def test_score_above_ten_is_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        upsert_anime(conn, Anime(anilist_id=900020, title="Bad Score", score=Decimal("11")))


def test_negative_episodes_are_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        upsert_anime(conn, Anime(anilist_id=900021, title="Bad Episodes", episodes=-1))


def test_negative_popularity_is_rejected(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        upsert_anime(conn, Anime(anilist_id=900023, title="Bad Popularity", popularity=-5))


def test_missing_title_is_rejected(conn):
    # Python type hints are not enforced at runtime, so None can reach the database.
    with pytest.raises(psycopg.errors.NotNullViolation):
        upsert_anime(conn, Anime(anilist_id=900022, title=None))


def test_link_to_missing_anime_is_rejected(conn):
    franchise_id = upsert_franchise(conn, Franchise("Test Franchise", "test"))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        link_anime_to_franchise(conn, anime_id=999999999, franchise_id=franchise_id)
