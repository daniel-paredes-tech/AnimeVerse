"""Repository: all the SQL lives here.

Rules followed by every function in this module:

- Values are always passed as query parameters (%(name)s), never formatted
  into the SQL string. This prevents SQL injection from untrusted API data.
- Functions never commit. The caller decides when a transaction is saved
  (conn.commit()) or undone (conn.rollback()).
- Database errors are not caught here. They propagate to the caller, which
  knows whether to skip one record or stop the whole import.
"""

from dataclasses import asdict
from typing import Any, NamedTuple

import psycopg

from animeverse.domain.models import Anime, Franchise


class SavedAnime(NamedTuple):
    id: int  # the anime's internal id
    created: bool  # True if the row was inserted, False if an existing row was refreshed


def _one_row(cursor: psycopg.Cursor[tuple[Any, ...]]) -> tuple[Any, ...]:
    """The single row a RETURNING or count query always produces."""
    row = cursor.fetchone()
    if row is None:  # cannot happen for these queries; fail loudly if it ever does
        raise RuntimeError("expected one row, got none")
    return row


def upsert_franchise(conn: psycopg.Connection, franchise: Franchise) -> int:
    """Insert a franchise, or update its search query if the name exists.

    Returns the franchise's id either way.
    """
    row = conn.execute(
        """
        INSERT INTO franchises (name, search_query)
        VALUES (%(name)s, %(search_query)s)
        ON CONFLICT (name) DO UPDATE
            SET search_query = EXCLUDED.search_query
        RETURNING id
        """,
        asdict(franchise),
    )
    franchise_id: int = _one_row(row)[0]
    return franchise_id


def upsert_anime(conn: psycopg.Connection, anime: Anime) -> SavedAnime:
    """Insert an anime, or update every field if its anilist_id already exists.

    Running this twice with the same anilist_id never creates a second row.
    created_at keeps its original value; updated_at is set to the current
    transaction time on every update.

    Returns the anime's internal id and whether the row is new. PostgreSQL
    tells us which case happened: xmax is 0 on a freshly inserted row and
    non-zero on a row that ON CONFLICT ... DO UPDATE just changed.
    """
    row = conn.execute(
        """
        INSERT INTO anime (
            anilist_id, mal_id, title, title_english, title_japanese, type,
            episodes, status, aired_from, aired_to, score, popularity,
            synopsis, image_url, anilist_url, start_year, end_year
        )
        VALUES (
            %(anilist_id)s, %(mal_id)s, %(title)s, %(title_english)s,
            %(title_japanese)s, %(type)s, %(episodes)s, %(status)s,
            %(aired_from)s, %(aired_to)s, %(score)s, %(popularity)s,
            %(synopsis)s, %(image_url)s, %(anilist_url)s,
            %(start_year)s, %(end_year)s
        )
        ON CONFLICT (anilist_id) DO UPDATE SET
            mal_id         = EXCLUDED.mal_id,
            title          = EXCLUDED.title,
            title_english  = EXCLUDED.title_english,
            title_japanese = EXCLUDED.title_japanese,
            type           = EXCLUDED.type,
            episodes       = EXCLUDED.episodes,
            status         = EXCLUDED.status,
            aired_from     = EXCLUDED.aired_from,
            aired_to       = EXCLUDED.aired_to,
            score          = EXCLUDED.score,
            popularity     = EXCLUDED.popularity,
            synopsis       = EXCLUDED.synopsis,
            image_url      = EXCLUDED.image_url,
            anilist_url    = EXCLUDED.anilist_url,
            start_year     = EXCLUDED.start_year,
            end_year       = EXCLUDED.end_year,
            updated_at     = now()
        RETURNING id, (xmax = 0) AS created
        """,
        asdict(anime),
    )
    anime_id, created = _one_row(row)
    return SavedAnime(id=anime_id, created=created)


def list_anime_by_franchise(conn: psycopg.Connection) -> dict[str, list[Anime]]:
    """Every franchise with its anime, for read-only display.

    Franchises are in alphabetical order; each franchise's anime are sorted by
    popularity (most popular first). Franchises without anime are included
    with an empty list.
    """
    rows = conn.execute(
        """
        SELECT f.name,
               a.anilist_id, a.title, a.mal_id, a.title_english, a.title_japanese,
               a.type, a.episodes, a.status, a.aired_from, a.aired_to, a.score,
               a.popularity, a.synopsis, a.image_url, a.anilist_url,
               a.start_year, a.end_year
        FROM franchises f
        LEFT JOIN anime_franchises af ON af.franchise_id = f.id
        LEFT JOIN anime a ON a.id = af.anime_id
        ORDER BY f.name, a.popularity DESC NULLS LAST, a.title
        """
    ).fetchall()

    result: dict[str, list[Anime]] = {}
    for franchise_name, *anime_columns in rows:
        anime_list = result.setdefault(franchise_name, [])
        if anime_columns[0] is not None:  # NULL anilist_id = franchise without anime
            anime_list.append(Anime(*anime_columns))
    return result


def link_anime_to_franchise(conn: psycopg.Connection, anime_id: int, franchise_id: int) -> bool:
    """Record that an anime belongs to a franchise.

    Returns True if the link was new, False if it already existed.
    """
    cursor = conn.execute(
        """
        INSERT INTO anime_franchises (franchise_id, anime_id)
        VALUES (%(franchise_id)s, %(anime_id)s)
        ON CONFLICT DO NOTHING
        """,
        {"franchise_id": franchise_id, "anime_id": anime_id},
    )
    return cursor.rowcount == 1
