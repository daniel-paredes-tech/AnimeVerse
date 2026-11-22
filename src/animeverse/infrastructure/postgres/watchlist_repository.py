"""SQL for the user's watchlist (table watchlist_entries, migration 0002).

Rules (the same as repository.py): values are always query parameters,
functions never commit and never catch database errors.
"""

import psycopg

from animeverse.application.ports import SavedEntry, StoredWatchlistEntry
from animeverse.domain.watchlist import WatchlistEntry


def upsert_entry(conn: psycopg.Connection, anime_id: int, entry: WatchlistEntry) -> SavedEntry:
    """Create the entry, or replace every field if the anime already has one.

    created_at keeps its first value; updated_at is set to now on a replace.
    As in repository.upsert_anime, xmax = 0 tells a fresh insert from an update.
    """
    row = conn.execute(
        """
        INSERT INTO watchlist_entries (anime_id, status, episodes_watched, rating, notes)
        VALUES (%(anime_id)s, %(status)s, %(episodes_watched)s, %(rating)s, %(notes)s)
        ON CONFLICT (anime_id) DO UPDATE SET
            status           = EXCLUDED.status,
            episodes_watched = EXCLUDED.episodes_watched,
            rating           = EXCLUDED.rating,
            notes            = EXCLUDED.notes,
            updated_at       = now()
        RETURNING created_at, updated_at, (xmax = 0) AS created
        """,
        {
            "anime_id": anime_id,
            "status": entry.status.value,
            "episodes_watched": entry.episodes_watched,
            "rating": entry.rating,
            "notes": entry.notes,
        },
    ).fetchone()
    if row is None:  # cannot happen with RETURNING; fail loudly if it ever does
        raise RuntimeError("expected one row, got none")
    created_at, updated_at, created = row
    return SavedEntry(StoredWatchlistEntry(anime_id, entry, created_at, updated_at), created=created)


def delete_entry(conn: psycopg.Connection, anime_id: int) -> bool:
    """Remove the anime's entry. False if it had none."""
    cursor = conn.execute("DELETE FROM watchlist_entries WHERE anime_id = %(anime_id)s", {"anime_id": anime_id})
    return cursor.rowcount == 1
