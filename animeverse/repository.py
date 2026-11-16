"""Repository: all database reads and writes live here.

Rules followed by every function in this module:

- Values are always passed as query parameters (%(name)s), never formatted
  into the SQL string. This prevents SQL injection from untrusted API data.
- Functions never commit. The caller decides when a transaction is saved
  (conn.commit()) or undone (conn.rollback()).
- Database errors are not caught here. They propagate to the caller, which
  knows whether to skip one record or stop the whole import.
"""

from dataclasses import asdict

import psycopg

from animeverse.config import DatabaseSettings
from animeverse.models import Anime, Franchise


def connect(settings: DatabaseSettings) -> psycopg.Connection:
    """Open a connection. A transaction starts automatically on the first query."""
    return psycopg.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        dbname=settings.dbname,
    )


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
    ).fetchone()
    return row[0]


def upsert_anime(conn: psycopg.Connection, anime: Anime) -> int:
    """Insert an anime, or update every field if its anilist_id already exists.

    Running this twice with the same anilist_id never creates a second row.
    created_at keeps its original value; updated_at is set to the current
    transaction time on every update.

    Returns the anime's internal id either way.
    """
    row = conn.execute(
        """
        INSERT INTO anime (
            anilist_id, mal_id, title, title_english, title_japanese, type,
            episodes, status, aired_from, aired_to, score, popularity,
            synopsis, image_url, anilist_url
        )
        VALUES (
            %(anilist_id)s, %(mal_id)s, %(title)s, %(title_english)s,
            %(title_japanese)s, %(type)s, %(episodes)s, %(status)s,
            %(aired_from)s, %(aired_to)s, %(score)s, %(popularity)s,
            %(synopsis)s, %(image_url)s, %(anilist_url)s
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
            updated_at     = now()
        RETURNING id
        """,
        asdict(anime),
    ).fetchone()
    return row[0]


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
