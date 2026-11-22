"""Watchlist entries: the user's own tracking of an anime (ADR 0011).

Revision ID: 0002
Revises: 0001
Created: 2026-11-23

Expand only: a new table, nothing existing changes. Imported data (anime,
franchises) and user data (this table) are kept apart, so an import can
never overwrite what the user wrote.

The rules that compare an entry with its anime (episodes watched can't
exceed the anime's episodes, "completed" means all of them...) live in the
domain (domain/watchlist.py), because they depend on another table. This
table only enforces what a single row can check, as a last line of defence.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE watchlist_entries (
    -- One entry per anime: AnimeVerse is a single-user local application, so
    -- the anime is the whole key. Several users would need a users table and a
    -- (user_id, anime_id) key instead (ADR 0011).
    -- ON DELETE CASCADE: an entry has no meaning without its anime. Imports
    -- never delete anime (ADR 0007), so this only matters for manual cleanup.
    anime_id          INTEGER PRIMARY KEY REFERENCES anime(id) ON DELETE CASCADE,
    -- Our own vocabulary, so a fixed list is right here (unlike anime.status,
    -- which holds AniList's values as free text so new ones never break an import).
    -- Lowercase, exactly as the API sends them.
    status            TEXT NOT NULL
                      CHECK (status IN ('planning', 'watching', 'completed', 'paused', 'dropped')),
    episodes_watched  INTEGER NOT NULL DEFAULT 0 CHECK (episodes_watched >= 0),
    rating            SMALLINT CHECK (rating BETWEEN 1 AND 10),    -- NULL: not rated
    -- NULL means "no notes". Empty or blank text is refused, so "no notes" has
    -- exactly one representation (the API turns blank notes into NULL).
    notes             TEXT CHECK (char_length(notes) <= 1000 AND btrim(notes) <> ''),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),   -- first added
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()    -- last replaced (set by the store)
);

-- No extra index: the primary key already covers lookups by anime and the
-- join from anime, and the filter by status scans a table of at most ~160 rows.
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    # Development only: AnimeVerse's migrations go forward (see docs/migrations.md).
    op.execute("DROP TABLE watchlist_entries")
