# AnimeVerse

A small data pipeline that imports anime from seven franchises from the public [AniList](https://anilist.co) API into a PostgreSQL database running in Docker. The import can be run any number of times without creating duplicates.

Built as a homework project for the Migracode training program. Everything runs locally; nothing is deployed.

## The API I chose, and why

**AniList** (`https://graphql.anilist.co`, GraphQL, no account or key needed).

- It is free for non-commercial use and its [terms](https://docs.anilist.co/guide/terms-of-use) allow this kind of project.
- Its rate limit is documented and also reported in the response headers, so the client can follow the real limit instead of a guessed one.
- It returns enough to browse: 166 results for my seven franchises, 163 after filtering.
- It reports the MyAnimeList id too, which keeps the data compatible with other anime sources.

I started with the Jikan API, but it was unreachable on the day I began, so I switched. That is also why the schema keeps a `mal_id` column.

## How to run it

You need [Docker](https://www.docker.com/) with Docker Compose and Python 3.11 or newer (developed and tested with 3.14).

```bash
# 1. Settings: copy the example and choose a password
cp .env.example .env             # then edit POSTGRES_PASSWORD (and POSTGRES_PORT if 5432 is busy)

# 2. Start PostgreSQL (db/schema.sql is applied on the first start)
docker compose up -d
docker compose ps                # wait for "healthy"

# 3. Python environment
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt

# 4. Run the import
.venv/bin/python -m animeverse.import_anime
```

The import ends with a report:

```
Franchise         Status   Fetched  Rejected  Excluded   New  Refreshed  New links
----------------------------------------------------------------------------------
Naruto            ok            26         0         0    26          0         26
...
Demon Slayer      ok            10         0         1     9          0          9

Excluded (not part of the franchise):
  - Demon Slayer: Onigiri (21612)

Result: 7 of 7 franchises imported.
```

Run it again and every row shows `New 0`: existing anime are refreshed, nothing is duplicated.

`db/schema.sql` only runs on an empty data volume. After changing it, reset the database with `docker compose down -v` (this deletes the data) and import again.

### Looking at the data

```bash
# Demo queries: counts, duplicates check, top anime, missing values
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < queries/demo.sql

# A SQL shell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# A read-only page in the browser, served on localhost only
.venv/bin/python -m animeverse.server --open
```

### Tests

```bash
.venv/bin/python -m pytest            # 142 tests; the database must be running
.venv/bin/python -m pytest -m live    # optional: one test against the real AniList API
```

The API client tests use a fake AniList and a fake clock, so they need no network and never really wait. The database tests use a separate `<POSTGRES_DB>_test` database, so imported data is never touched.

## What surprised me in the data

Numbers are from an import of 163 anime on 2026-11-16.

**In the API**

- **"Plain text" descriptions contain HTML.** I asked for `description(asHtml: false)` and 134 of 163 descriptions still had tags like `<br>`, `<i>` and `<li>`, plus entities like `&mdash;`. The parser converts them to plain text.
- **Search is loose.** The top result for "Demon Slayer" was *Onigiri*, an unrelated anime about an online game. So the import keeps a result only if its title contains one of the franchise's match terms.
- **The result count cannot be trusted.** A search for "naruto" reports 5,000 results in 2,500 pages, but everything fits on one page of 50. AniList's docs confirm that only `hasNextPage` is reliable.
- **The page size is capped silently.** Asking for 100 per page returns 50 with no error.
- **The real rate limit is a third of the documented one.** The docs say 90 requests per minute; the API is currently in a "degraded state" and the `X-RateLimit-Limit` header says 30.

**In the anime**

- **Dates are often incomplete.** 11 anime have no full start date, but 6 of those do have a year: unreleased ones (*THE ONE PIECE*, 2027) and old ones where only the year was recorded (*Dragon Ball Specials*, 1988). At first I stored partial dates as `NULL` and lost those years; now the year has its own column.
- **Title matching has a false positive.** Showing the years exposed *Mizuiro no One-Piece*, a music video from 1982, inside the One Piece franchise, which started in 1999. The title means "light blue one-piece dress". It matches the term "one piece" but has nothing to do with the franchise.
- **Movies outnumber TV series**: 62 movies and 41 TV series. One Piece has 39 entries, but only 2 are TV series.
- **The longest-running show has no episode count.** One Piece is still airing, so AniList reports its episodes as unknown.
- **AniList and MyAnimeList ids are different numbers** for 77 of the 158 anime that have both; 5 have no MyAnimeList id.
- **Many values are missing**: 34 anime have no English title, 8 no score, 6 no episode count.

## How it is built

```
AniList API ──► client ──► parser ──► importer ──► repository ──► PostgreSQL
```

| Module | What it does |
|---|---|
| `anilist_client.py` | Calls the API. 10 s timeout; retries timeouts, network errors and 5xx responses with backoff (1 s, 2 s, 4 s); on `429` waits for `Retry-After` (up to 2 minutes); spaces requests using the `X-RateLimit-Limit` header; follows `hasNextPage`. |
| `parser.py` | Turns raw API items into `Anime` models. An item without a valid id or title is rejected; an invalid optional value becomes `NULL` with a warning. One bad item never stops the others. |
| `importer.py` | Runs client → parser → franchise filter → repository for each franchise and builds the report. |
| `repository.py` | The only module with SQL. Parameterized queries and `INSERT … ON CONFLICT` upserts. |
| `models.py`, `franchises.py`, `config.py` | The data models, the list of franchises, and the settings read from `.env`. |
| `server.py`, `page.py` | The read-only local page. |

**Schema** ([`db/schema.sql`](db/schema.sql)): `franchises`, `anime` and the link table `anime_franchises` (many-to-many). `anime.anilist_id` is `UNIQUE` and is the key the import upserts on. `CHECK` constraints refuse impossible values such as a score above 10.

**Idempotency.** Each table has a unique key and each insert says what to do on a conflict:

| Table | Statement | Running twice |
|---|---|---|
| `franchises` | `ON CONFLICT (name) DO UPDATE` | one row |
| `anime` | `ON CONFLICT (anilist_id) DO UPDATE` | one row per anime, values refreshed, `created_at` kept |
| `anime_franchises` | `ON CONFLICT DO NOTHING` | existing links skipped |

**Failures.** Each franchise is one transaction. If AniList or the database fails for a franchise, it is rolled back and the next one still runs. If the database refuses a single anime, only that anime is skipped (a savepoint) and it is listed in the report.

**Dates and time zones.** AniList sends dates as `{year, month, day}` with no time and no time zone, and any part can be missing. A complete date is stored as a `DATE`; an incomplete one is not guessed, but its year is kept in `start_year` / `end_year`. The only timestamps are my own `created_at` and `updated_at`, stored as `TIMESTAMPTZ`.

**Scores.** AniList's `weightedScore` (0–100) is stored as a 0–10 decimal (`85` → `8.50`).

## Limitations

- Franchise membership is decided by the title, so it can be wrong both ways: a spin-off with a different name is excluded until a match term is added (the report lists everything excluded), and an unrelated title that contains the term is included (see *Mizuiro no One-Piece* above). AniList's `relations` field would be a better source.
- Imports never delete. An anime that disappears from AniList, or stops matching, stays in the database.
- Every run fetches every franchise again: one request each, about 12 seconds in total.

Anime data comes from the [AniList API](https://docs.anilist.co). This project is not affiliated with AniList.
