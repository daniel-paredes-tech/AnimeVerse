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
- **The local page** (`animeverse.server`) listens on `127.0.0.1` only, refuses requests for any other host name, and loads nothing from outside (no images, fonts or scripts).
- **Tests** need no internet connection (except the optional `live` test, which you must ask for explicitly).
- **The application is not deployed or hosted anywhere.** There is no public website or remote service; the source code is on GitHub.

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
| `server.py` | A private, read-only local page (Python's standard `http.server`) with the stored data. |
| `page.py` | Turns the stored data into that page's HTML, escaping every value. |

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

To add a franchise, add one line to `animeverse/franchises.py`.

## Viewing the data

There are three ways to look at what's stored (the database must be running).

**1. Local page in your browser**

```bash
.venv/bin/python -m animeverse.server --open     # http://localhost:8000
```

Shows every franchise and its anime (title, type, episodes, status, score, year), most popular first. It is read-only: it never calls AniList and never changes the database. Stop it with `Ctrl+C`. If port 8000 is busy, use `--port 8001`.

**2. Demo queries in the terminal**

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < queries/demo.sql
```

Runs the queries in [`queries/demo.sql`](queries/demo.sql): rows per table, anime per franchise, a proof that no anime is stored twice, top anime by score and popularity, and missing values per column.

**3. Your own SQL**

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Opens a PostgreSQL shell without typing the password. Type `\dt` to list the tables and `\q` to quit.

## Tests

```bash
.venv/bin/python -m pytest                    # all tests (the database must be running)
.venv/bin/python -m pytest tests/test_parser.py
.venv/bin/python -m pytest -m live            # opt-in: one test against the real AniList API
```

- **131 tests**, covering the API client (successful responses, timeouts, retries, rate limits, error responses), the parser (validation, missing and malformed fields, real AniList samples), the repository (upserts, duplicate prevention, constraints, reading for display), the import service (repeated imports, failures in one franchise, rollback) and the local page (HTML escaping, security headers, refusing other hosts and methods).
- API client tests use `httpx.MockTransport` and a fake clock: no network, and no real waiting.
- Database tests use a separate `<POSTGRES_DB>_test` database, rebuilt from `db/schema.sql` on every run, so your imported data is never touched.
- The `live` test is skipped by default, so normal runs never depend on AniList being online.

## Key decisions

- **AniList instead of Jikan.** The project started with the Jikan API, but on 2026-11-16 Jikan's API was unreachable for everyone (checked from six countries). AniList was chosen over Kitsu because its rate limits are documented and reported in response headers, its documentation is actively maintained, and it reports the MyAnimeList id for compatibility.
- **Franchise filtering by title.** AniList's search is loose, so an anime is kept only if its romaji or English title contains one of the franchise's match terms (ignoring case, accents and punctuation). Checked against real results: 163 of 166 kept; the 3 excluded are listed in every import report.
- **Plain-text descriptions.** AniList returns HTML in descriptions even when plain text is requested, so the parser converts it to plain text and keeps the "(Source: …)" credits to the original writers.
- **Score and popularity.** AniList's `weightedScore` (0–100) is stored as a 0–10 decimal. `popularity` is the number of AniList users with the anime on their list; AniList's per-format rankings were not used because they aren't comparable across formats.
- **Imports never delete.** An anime that disappears from AniList's search results is kept.

## What the data revealed

Findings from the imported data (163 anime, imported on 2026-11-16) and from exploring the API. Scores and popularity change over time, so the numbers are a snapshot.

### In the anime data

- **Movies outnumber TV series.** Of the 163 anime, 62 are movies and only 41 are TV series; the rest are specials, OVAs, ONAs and music videos. One Piece is the extreme case: 39 entries, but only 2 TV series and 16 movies.
- **The longest-running show has no episode count.** One Piece is still airing, so AniList reports its episodes as unknown. The longest series with a known count is *Naruto: Shippuuden* (500 episodes).
- **Newer franchises score higher.** Demon Slayer (8.08), Attack on Titan (8.02) and Jujutsu Kaisen (7.98) have the highest average scores; Dragon Ball (6.78) and Yu-Gi-Oh! (6.52) the lowest. The three most popular anime are also from the newer franchises: the first seasons of *Attack on Titan*, *Demon Slayer* and *Jujutsu Kaisen*, each on about a million users' lists.
- **A one-off special ties for the highest score.** *ONE PIECE FAN LETTER* (a special) scores 8.90, the same as *Attack on Titan Season 3 Part 2*.
- **AniList and MyAnimeList ids are different numbers.** For 77 of the 158 anime that have both ids, they differ (for example, *Attack on Titan: The Final Season* is 110277 on AniList and 40028 on MyAnimeList). 5 anime have no MyAnimeList id at all.
- **Many values are simply missing.** 34 anime have no English title, 11 have no start date, 8 have no score and 6 have no episode count. They are mostly unreleased or still-airing anime.
- **Spin-offs don't always carry the franchise name.** *Juju Sanpo* (Jujutsu Kaisen) and *Kimetsu Gakuen* (Demon Slayer) would have been filtered out without extra match terms.

### In the AniList API

- **"Plain text" descriptions contain HTML.** Even with `description(asHtml: false)`, 134 of the 163 descriptions in the search results contained tags such as `<br>`, `<i>` and `<li>`, and some contained entities such as `&mdash;`. About two thirds end with a credit like "(Source: Anime News Network)".
- **Search returns unrelated results.** The top result for "Demon Slayer" was *Onigiri*, an anime about an online game.
- **The result count is not reliable.** A search for "naruto" reported 5,000 results across 2,500 pages, yet everything fits on one page of 50. AniList's docs confirm that `total` and `lastPage` are currently inaccurate; only `hasNextPage` can be trusted.
- **Page size is silently capped.** Asking for 100 results per page returns 50, without any error.
- **The documented score field is deprecated.** `averageScore` is marked as deprecated in AniList's own schema, in favour of `weightedScore`.
- **The rate limit is a third of the documented one.** The docs give 90 requests per minute, but the API currently runs in a "degraded state" at 30, and the `X-RateLimit-Limit` response header reports 30.

## Limitations

- An anime whose title doesn't mention its franchise (a spin-off with a different name) is excluded until a match term is added. The report always lists excluded anime, so nothing disappears silently.
- Partial dates (for example, only the year is known) are stored as `NULL` rather than guessed.
- Every run fetches every franchise again (one request each); fine for a handful of franchises.

## Data source and terms

Anime data comes from the [AniList API](https://docs.anilist.co). AniList's [terms of use](https://docs.anilist.co/guide/terms-of-use) allow free non-commercial use and prohibit mass collection of data; this project imports only a small, fixed set of franchises. AnimeVerse is not affiliated with AniList.
