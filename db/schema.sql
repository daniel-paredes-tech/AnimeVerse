-- AnimeVerse database schema
--
-- Three tables:
--   franchises        our own list of franchises (Jikan has no franchise concept)
--   anime             one row per anime, with the fields imported from Jikan
--   anime_franchises  links anime to franchises (many-to-many)
--
-- PostgreSQL runs this file automatically the first time the container starts
-- with an empty data volume (see docker-compose.yml).

CREATE TABLE franchises (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,        -- display name, e.g. 'Attack on Titan'
    search_query  TEXT NOT NULL,               -- the value sent to Jikan as q=...
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE anime (
    -- Internal identity, independent of MyAnimeList.
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- External identity: the MyAnimeList ID from Jikan. Imports upsert on this column.
    mal_id          INTEGER NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    title_english   TEXT,
    title_japanese  TEXT,
    -- Stored as free text, not a fixed list: the values are scraped from
    -- MyAnimeList, and a new value must not make valid anime fail to import.
    type            TEXT,
    episodes        INTEGER CHECK (episodes >= 0),
    status          TEXT,
    -- Jikan sends ISO 8601 timestamps that are always midnight; the parser
    -- converts them to dates.
    aired_from      DATE,
    aired_to        DATE,
    -- Exact decimal (e.g. 8.53). The CHECKs are a last line of defence:
    -- the parser should reject impossible values before they get here.
    score           NUMERIC(4,2) CHECK (score BETWEEN 0 AND 10),
    rank            INTEGER,
    popularity      INTEGER,
    synopsis        TEXT,
    image_url       TEXT,
    mal_url         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- first imported
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()    -- last refreshed by an import
);

CREATE TABLE anime_franchises (
    franchise_id  INTEGER NOT NULL REFERENCES franchises(id) ON DELETE CASCADE,
    anime_id      INTEGER NOT NULL REFERENCES anime(id)      ON DELETE CASCADE,
    -- franchise_id comes first so "all anime in a franchise" uses this index.
    PRIMARY KEY (franchise_id, anime_id)
);
