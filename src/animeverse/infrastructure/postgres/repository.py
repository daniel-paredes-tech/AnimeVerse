"""Repository: the importer's SQL (franchises, anime, links).

The API's SQL is in its sibling modules: catalog_queries.py (browsing) and
watchlist_repository.py (the user's watchlist). They follow the same rules.

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


def unlink_anime_except(
    conn: psycopg.Connection, franchise_id: int, keep_anilist_ids: list[int]
) -> list[tuple[int, int, str]]:
    """Remove the franchise's links to every anime whose AniList id is not in keep_anilist_ids.

    Links to other franchises are untouched. Returns (id, anilist_id, title) of
    each anime whose link was removed, ordered by AniList id.
    """
    cursor = conn.execute(
        """
        DELETE FROM anime_franchises AS af
        USING anime AS a
        WHERE af.anime_id = a.id
          AND af.franchise_id = %(franchise_id)s
          AND a.anilist_id <> ALL(%(keep)s)
        RETURNING a.id, a.anilist_id, a.title
        """,
        {"franchise_id": franchise_id, "keep": keep_anilist_ids},
    )
    rows = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
    return sorted(rows, key=lambda row: row[1])  # RETURNING has no ORDER BY


def delete_orphan_anime(conn: psycopg.Connection, anime_ids: list[int]) -> set[int]:
    """Delete those of the given anime that belong to no franchise and have no watchlist entry.

    The watchlist is the user's data: an anime in it is never deleted here.
    Returns the ids of the deleted anime.
    """
    cursor = conn.execute(
        """
        DELETE FROM anime AS a
        WHERE a.id = ANY(%(ids)s)
          AND NOT EXISTS (SELECT 1 FROM anime_franchises af WHERE af.anime_id = a.id)
          AND NOT EXISTS (SELECT 1 FROM watchlist_entries w WHERE w.anime_id = a.id)
        RETURNING a.id
        """,
        {"ids": anime_ids},
    )
    return {row[0] for row in cursor.fetchall()}
