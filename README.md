# AnimeVerse

A local data pipeline that imports anime from several franchises from the public [AniList](https://anilist.co) GraphQL API into a PostgreSQL database. Imports are safe to run any number of times.

AnimeVerse is an educational project, built as part of the Migracode training program. The focus is on correctness, testing and good engineering practice rather than size.

## What it does

For each configured franchise (Naruto, Jujutsu Kaisen, Yu-Gi-Oh!, One Piece, Dragon Ball, Attack on Titan, Demon Slayer), the import:

1. **searches AniList** for the franchise, respecting the API's rate limits;
2. **validates and cleans** every result (untrusted data: wrong types, partial dates, HTML in descriptions…);
3. **filters out search noise**, keeping only anime whose title matches the franchise (for example, a search for "Demon Slayer" also returns an unrelated anime called *Onigiri*);
4. **saves** the franchise, its anime and the links between them in PostgreSQL, in one transaction.

A real run imports 163 anime in about 12 seconds. Running it again creates nothing new: it refreshes existing rows.

## Runs locally

Everything runs on your own computer:

- **PostgreSQL** runs in a local Docker container, and its port is bound to `127.0.0.1`, so it can't be reached from other devices on your network.
- **Tests** need no internet connection (except the optional `live` test, which you must ask for explicitly).
- **Nothing is published or hosted anywhere.** There is no server, website or remote service.

The only outside connection is the **import** itself: it sends one search request per franchise to the AniList API to download the anime data. No account, key or personal information is sent.

## Architecture

```
AniList API ──► client ──► parser ──► import service ──► repository ──► PostgreSQL
              (network)  (validation) (orchestration)    (SQL only)     (Docker)
```

Each layer has one responsibility and lives in its own module in `animeverse/`:

| Module | Responsibility |
|---|---|
| `anilist_client.py` | Talks to AniList: GraphQL query, 10 s timeouts, retries with exponential backoff (1 s, 2 s, 4 s) for timeouts and 5xx errors, waits for `Retry-After` on `429`, spaces requests using the `X-RateLimit-Limit` header, follows `hasNextPage` pagination. Returns raw data only. |
| `parser.py` | Turns raw AniList items into `Anime` models. Rejects items without a valid `id` or title; turns invalid optional values into `NULL` with a warning; converts scores (0–100 → 0–10), dates (`{year, month, day}` → `DATE`) and descriptions (HTML → plain text). One malformed item never stops the others. |
| `importer.py` | Runs client → parser → franchise filter → repository for each franchise, with one transaction per franchise, and produces a report. |
| `repository.py` | All SQL: parameterized queries and `INSERT … ON CONFLICT` upserts. Never commits; the caller decides. |
| `models.py` | Internal data models (`Franchise`, `Anime`), separate from AniList's response format. |
| `franchises.py` | The list of franchises to import: name, search text and title match terms. |
| `config.py` | Reads settings from `.env`; the password never appears in logs or error messages. |
| `import_anime.py` | The command that runs the import. |

## Data model

```
franchises (id, name UNIQUE, search_query)
     │ 1
     │        anime_franchises (franchise_id, anime_id)   PRIMARY KEY on both
     │ *                 │ *
     └───────────────────┘
                         │ 1
anime (id, anilist_id UNIQUE, mal_id, title, title_english, title_japanese, type,
       episodes, status, aired_from, aired_to, score, popularity, synopsis,
       image_url, anilist_url, created_at, updated_at)
```

- `anilist_id` (AniList's own id) is the key used to avoid duplicates. `mal_id` (the MyAnimeList id reported by AniList) is optional reference data.
- `anime_franchises` is a many-to-many link table, so an anime could belong to more than one franchise without anything being overwritten.
- `CHECK` constraints reject impossible values (score outside 0–10, negative episodes or popularity) as a last line of defence behind the parser.

The full schema, with comments explaining each choice, is in [`db/schema.sql`](db/schema.sql).

## How repeated imports stay safe

| Table | Statement | Effect of running twice |
|---|---|---|
| `franchises` | `ON CONFLICT (name) DO UPDATE` | One row; search text refreshed |
| `anime` | `ON CONFLICT (anilist_id) DO UPDATE` | One row per anime; values such as score and popularity refreshed, `created_at` kept |
| `anime_franchises` | `ON CONFLICT DO NOTHING` | Existing links skipped |

Each franchise is imported in **one transaction**: if anything fails, that franchise is rolled back and left exactly as it was, and the import continues with the next franchise.

## Requirements

- [Docker](https://www.docker.com/) with Docker Compose (for PostgreSQL 18)
- Python 3.14 (on macOS: `brew install python@3.14`; the system Python is too old)

No AniList account or API key is needed.

## Setup

```bash
# 1. Configuration: copy the example and choose your own password
cp .env.example .env
#    then edit .env and replace POSTGRES_PASSWORD=change_me
#    (if port 5432 is already used on your machine, change POSTGRES_PORT)

# 2. Start PostgreSQL (the schema is created automatically on first start)
docker compose up -d
docker compose ps            # wait until the status says "healthy"

# 3. Python environment and dependencies
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Usage

```bash
.venv/bin/python -m animeverse.import_anime
```

The command logs each step and ends with a summary like this:

```
Franchise         Status   Fetched  Rejected  Excluded   New  Refreshed  New links
----------------------------------------------------------------------------------
Naruto            ok            26         0         0    26          0         26
...
Demon Slayer      ok            10         0         1     9          0          9

Excluded (not part of the franchise):
  - Demon Slayer: Onigiri (21612)
  ...

Result: 7 of 7 franchises imported.
```

Exit codes: `0` all franchises imported, `1` at least one franchise failed, `2` the import could not start (missing settings or database unreachable).

To look at the data:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

To add a franchise, add one line to `animeverse/franchises.py`.

## Tests

```bash
.venv/bin/python -m pytest                    # all tests (the database must be running)
.venv/bin/python -m pytest tests/test_parser.py
.venv/bin/python -m pytest -m live            # opt-in: one test against the real AniList API
```

- **97 tests**, covering the API client (successful responses, timeouts, retries, rate limits, error responses), the parser (validation, missing and malformed fields, real AniList samples), the repository (upserts, duplicate prevention, constraints) and the import service (repeated imports, failures in one franchise, rollback).
- API client tests use `httpx.MockTransport` and a fake clock: no network, and no real waiting.
- Database tests use a separate `<POSTGRES_DB>_test` database, rebuilt from `db/schema.sql` on every run, so your imported data is never touched.
- The `live` test is skipped by default, so normal runs never depend on AniList being online.

## Key decisions

- **AniList instead of Jikan.** The project started with the Jikan API, but on 2026-11-16 Jikan's API was unreachable for everyone (checked from six countries). AniList was chosen over Kitsu because its rate limits are documented and reported in response headers, its documentation is actively maintained, and it reports the MyAnimeList id for compatibility.
- **Franchise filtering by title.** AniList's search is loose, so an anime is kept only if its romaji or English title contains one of the franchise's match terms (ignoring case, accents and punctuation). Checked against real results: 163 of 166 kept; the 3 excluded are listed in every import report.
- **Plain-text descriptions.** AniList returns HTML in descriptions even when plain text is requested, so the parser converts it to plain text and keeps the "(Source: …)" credits to the original writers.
- **Score and popularity.** AniList's `weightedScore` (0–100) is stored as a 0–10 decimal. `popularity` is the number of AniList users with the anime on their list; AniList's per-format rankings were not used because they aren't comparable across formats.
- **Imports never delete.** An anime that disappears from AniList's search results is kept.

## Limitations

- An anime whose title doesn't mention its franchise (a spin-off with a different name) is excluded until a match term is added. The report always lists excluded anime, so nothing disappears silently.
- Partial dates (for example, only the year is known) are stored as `NULL` rather than guessed.
- Every run fetches every franchise again (one request each); fine for a handful of franchises.

## Data source and terms

Anime data comes from the [AniList API](https://docs.anilist.co). AniList's [terms of use](https://docs.anilist.co/guide/terms-of-use) allow free non-commercial use and prohibit mass collection of data; this project imports only a small, fixed set of franchises. AnimeVerse is not affiliated with AniList.
