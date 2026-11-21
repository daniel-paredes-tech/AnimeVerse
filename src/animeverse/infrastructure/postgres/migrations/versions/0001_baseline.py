"""Baseline: the three tables, as they were before migrations existed.

Revision ID: 0001
Revises: (none)
Created: 2026-11-21

This is the schema that db/schema.sql created. A database that already has
these tables (created by db/schema.sql) is marked as being at this revision
with `alembic stamp 0001` instead of running it.

Three tables:
  franchises        our own list of franchises (AniList has no franchise concept)
  anime             one row per anime, with the fields imported from AniList
  anime_franchises  links anime to franchises (many-to-many)
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = """
CREATE TABLE franchises (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,        -- display name, e.g. 'Attack on Titan'
    search_query  TEXT NOT NULL,               -- the search text sent to AniList
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE anime (
    -- Internal identity, independent of any external service.
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- External identity: AniList's media id (never null in AniList's schema).
    -- Imports upsert on this column.
    anilist_id      INTEGER NOT NULL UNIQUE,
    -- MyAnimeList id as reported by AniList (idMal). Optional and not unique:
    -- it is untrusted reference data, kept for compatibility with MAL/Jikan.
    mal_id          INTEGER,
    title           TEXT NOT NULL,                -- AniList title.romaji
    title_english   TEXT,
    title_japanese  TEXT,                         -- AniList title.native
    -- Stored as free text, not a fixed list (AniList values such as 'TV',
    -- 'TV_SHORT', 'FINISHED'): a new value must not make valid anime fail to import.
    type            TEXT,                         -- AniList format
    episodes        INTEGER CHECK (episodes >= 0),
    status          TEXT,
    -- AniList sends dates as {year, month, day}, and often only part of a date
    -- is known (e.g. an anime announced for "2027"). A DATE needs all three
    -- parts, so aired_from/aired_to are NULL unless the date is complete; the
    -- parser never invents a month or a day. The year is stored on its own so
    -- that a known year is not lost with the rest of a partial date.
    -- These are calendar dates without a time or a time zone.
    aired_from      DATE,
    aired_to        DATE,
    start_year      INTEGER CHECK (start_year > 0),
    end_year        INTEGER CHECK (end_year > 0),
    -- 0-10 exact decimal: the parser converts AniList's 0-100 weightedScore
    -- (85 -> 8.50). The CHECKs are a last line of defence: the parser should
    -- reject impossible values before they get here.
    score           NUMERIC(4,2) CHECK (score BETWEEN 0 AND 10),
    -- Number of AniList users with this anime on their list.
    popularity      INTEGER CHECK (popularity >= 0),
    synopsis        TEXT,
    image_url       TEXT,
    anilist_url     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- first imported
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()    -- last refreshed by an import
);

CREATE TABLE anime_franchises (
    franchise_id  INTEGER NOT NULL REFERENCES franchises(id) ON DELETE CASCADE,
    anime_id      INTEGER NOT NULL REFERENCES anime(id)      ON DELETE CASCADE,
    -- franchise_id comes first so "all anime in a franchise" uses this index.
    PRIMARY KEY (franchise_id, anime_id)
);

-- The primary key above only helps lookups that start from a franchise. This
-- index covers the other direction: "which franchises is this anime in?", and
-- the ON DELETE CASCADE check when an anime is deleted.
CREATE INDEX anime_franchises_anime_id_idx ON anime_franchises (anime_id);
"""


def upgrade() -> None:
    op.execute(SCHEMA)


def downgrade() -> None:
    # Development only: AnimeVerse's migrations go forward (see docs/migrations.md).
    op.execute("DROP TABLE anime_franchises, anime, franchises")
