# AnimeVerse

A small data pipeline that imports anime from seven franchises from the public [AniList](https://anilist.co) API into a PostgreSQL database running in Docker. The import can be run any number of times without creating duplicates. A REST API, described by an OpenAPI contract, serves the data, and a web UI shows it as a universe map of the franchises, with a personal watchlist.

Built as a homework project for the Migracode training program. Everything runs locally; nothing is deployed.

## The API I chose, and why

**AniList** (`https://graphql.anilist.co`, GraphQL, no account or key needed).

- It is free for non-commercial use and its [terms](https://docs.anilist.co/guide/terms-of-use) allow this kind of project.
- Its rate limit is documented and also reported in the response headers, so the client can follow the real limit instead of a guessed one.
- It returns enough to browse: 166 results for my seven franchises, 162 after filtering.
- It reports the MyAnimeList id too, which keeps the data compatible with other anime sources.

I started with the Jikan API, but it was unreachable on the day I began, so I switched. That is also why the schema keeps a `mal_id` column.

## How to run it

You need [Docker](https://www.docker.com/) with Docker Compose and Python 3.11 or newer (developed and tested with 3.14).

```bash
# 1. Settings: copy the example and choose a password
cp .env.example .env             # then edit POSTGRES_PASSWORD (and POSTGRES_PORT if 5432 is busy)

# 2. Start PostgreSQL
docker compose up -d
docker compose ps                # wait for "healthy"

# 3. Python environment
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

# 4. Create or update the tables, then run the import
.venv/bin/animeverse migrate
.venv/bin/animeverse import
```

Or run the application in Docker too, without a Python environment (step 3 not needed):

```bash
docker compose run --rm migrate
docker compose run --rm import       # runs migrate first
```

The import ends with a report:

```
Franchise         Status   Fetched  Rejected  Excluded   New  Refreshed  New links  Unlinked  Deleted
-----------------------------------------------------------------------------------------------------
Naruto            ok            26         0         0    26          0         26         0        0
...
Demon Slayer      ok            10         0         1     9          0          9         0        0

Excluded (not part of the franchise):
  - Demon Slayer: Onigiri (21612)

Result: 7 of 7 franchises imported.
```

Run it again and every row shows `New 0`: existing anime are refreshed, nothing is duplicated. If an anime stops belonging to a franchise, it is unlinked from it, and deleted if it is in no other franchise and not on the watchlist.

Exit codes: `0` success, `1` at least one franchise failed, `2` could not start (missing settings, database unreachable).

The database schema is created and changed only by numbered migrations (Alembic). `animeverse migrate` applies the ones your database doesn't have yet, so it is safe to run every time. See [docs/migrations.md](docs/migrations.md) before changing the schema.

All settings are environment variables, read from `.env` locally; [`.env.example`](.env.example) lists every one.

### Looking at the data

```bash
# Demo queries: counts, duplicates check, top anime, missing values
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < queries/demo.sql

# A SQL shell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# The web UI and the REST API, on this computer only (build the UI once first, see below)
.venv/bin/animeverse serve --open                          # http://localhost:8000
curl "http://localhost:8000/v1/anime?status=RELEASING"     # e.g. what is airing now
```

### The web UI

A React + Vite + TypeScript app in [`web/`](web/), built only from `openapi.yaml`: its API types are
generated from the contract, so the build fails if the UI uses something the contract doesn't offer.

```bash
cd web
npm ci                # install exactly what package-lock.json lists (Node.js 26)
npm run build         # web/dist, which `animeverse serve` then serves at /
npm run dev           # or: a dev server on :5173 that sends /v1 to the API on :8000
```

- **Universe** (`/`): the seven franchises as constellations in a screentoned night sky. A star's size is
  its popularity and its dot density its score; hover a star for its card, click a franchise to zoom in.
  Beside it: what is airing now, what is coming, and what you are watching.
- **Browse** (`/anime`): every filter, sort and page the API offers, kept in the URL.
- **Detail** (`/anime/42`): everything stored about one anime, and your watchlist entry, whose form shows the
  API's own validation messages next to each field.

The design (a weekly manga magazine issue) is described in [DESIGN.md](DESIGN.md). It is built and checked
for desktop screens.

### The API

`openapi.yaml` is the contract: it was written before the code, and the server is
tested against it ([ADR 0010](docs/adr/0010-contract-first-openapi.md)). The running
API serves it at `/v1/openapi.yaml`.

| Endpoint | What it does |
|---|---|
| `GET /v1/anime` | List with filters (`q`, `franchise`, `status`, `format`, `year_from`, `year_to`, `min_score`, `on_watchlist`, `watchlist_status`), `sort` and pages |
| `GET /v1/anime/{id}` | One anime, with its franchises and your watchlist entry |
| `PUT` / `DELETE /v1/anime/{id}/watchlist-entry` | Create, replace or remove your watchlist entry (validated) |
| `GET /v1/franchises` | Every franchise with its number of anime |

Every error is an RFC 9457 Problem Details JSON (`application/problem+json`) with the
same fields; a 400 or 422 lists each invalid field with a stable `code`.

```bash
npx @redocly/cli lint openapi.yaml    # lint the contract (needs Node.js)
```

### Tests and checks

```bash
.venv/bin/python -m pytest            # every test, including the API contract tests; the database must be running
.venv/bin/python -m pytest -m live    # optional: one test against the real AniList API
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint and formatting
.venv/bin/mypy                        # types (strict)
.venv/bin/lint-imports                # architecture rules
cd web && npm run gen:api && npm run typecheck && npm test && npm run build   # the web UI
```

GitHub Actions runs all of them on every push, on Python 3.11 and 3.14, and builds the container image.
Every version is pinned exactly; Dependabot (`.github/dependabot.yml`) opens weekly pull requests to update them, and CI checks each one.

- **Unit tests** check the import logic with in-memory fakes: no network, no database.
- **Contract tests** run the same checks against the in-memory store and the real PostgreSQL store, which proves the fake behaves like the real thing.
- **API client tests** use a fake AniList and a fake clock, so they test timeouts, retries and rate limits without network and without really waiting.
- **Database tests** use a separate `<POSTGRES_DB>_test` database built by running every migration, so imported data is never touched.
- **Guard tests** fail if a committed migration is edited, if a migration removes something outside a "contract" migration, or if a layer imports one it shouldn't.

## What surprised me in the data

Numbers are from an import of 163 anime on 2026-11-16.

**In the API**

- **"Plain text" descriptions contain HTML.** I asked for `description(asHtml: false)` and 134 of 163 descriptions still had tags like `<br>`, `<i>` and `<li>`, plus entities like `&mdash;`. The mapper converts them to plain text.
- **Search is loose.** The top result for "Demon Slayer" was *Onigiri*, an unrelated anime about an online game. So the import keeps a result only if AniList's `relations` connect it to the franchise's main anime ([ADR 0012](docs/adr/0012-membership-by-relations-and-link-reconciliation.md)). At first I matched titles instead, which caused the next finding.
- **The result count cannot be trusted.** A search for "naruto" reports 5,000 results in 2,500 pages, but everything fits on one page of 50. AniList's docs confirm that only `hasNextPage` is reliable.
- **The page size is capped silently.** Asking for 100 per page returns 50 with no error.
- **The real rate limit is a third of the documented one.** The docs say 90 requests per minute; the API is currently in a "degraded state" and the `X-RateLimit-Limit` header says 30.

**In the anime**

- **Dates are often incomplete.** 11 anime have no full start date, but 6 of those do have a year: unreleased ones (*THE ONE PIECE*, 2027) and old ones where only the year was recorded (*Dragon Ball Specials*, 1988). At first I stored partial dates as `NULL` and lost those years; now the year has its own column.
- **Title matching has a false positive.** Showing the years exposed *Mizuiro no One-Piece*, a music video from 1982, inside the One Piece franchise, which started in 1999. The title means "light blue one-piece dress". It matches the term "one piece" but has nothing to do with the franchise. Deciding membership by relations removed it, together with a second one, *Noroi no One Piece*.
- **Movies outnumber TV series**: 62 movies and 41 TV series. One Piece has 39 entries, but only 2 are TV series.
- **The longest-running show has no episode count.** One Piece is still airing, so AniList reports its episodes as unknown.
- **AniList and MyAnimeList ids are different numbers** for 77 of the 158 anime that have both; 5 have no MyAnimeList id.
- **Many values are missing**: 34 anime have no English title, 8 no score, 6 no episode count.

## How it is built

A hexagonal architecture (ports and adapters): four layers, and dependencies only point inwards, towards the domain.

```
entrypoints ──► infrastructure ──► application ──► domain
 (CLI, API)      (AniList,          (use cases,      (models,
                  PostgreSQL)        ports)           rules)
```

```
src/animeverse/
  domain/           models.py (Anime, Franchise) · membership.py (which search results belong to a franchise)
                    watchlist.py (a watchlist entry and its rules)
  application/      ports.py (the contracts: AnimeSource, CatalogStore, CatalogQuery, WatchlistStore… and their errors)
                    import_catalog.py · catalog.py · watchlist.py (the use cases) · errors.py
  infrastructure/
    anilist/        client.py (HTTP) · mapper.py (AniList JSON → Anime) · source.py (the AnimeSource port)
    postgres/       repository.py · catalog_queries.py · watchlist_repository.py (the SQL)
                    store.py (the store ports) · migrations/ (Alembic)
  config/           settings.py (environment variables) · franchises.py (what to import)
  entrypoints/      cli.py (the `animeverse` command; the only place that picks adapters)
                    api/ (the REST API: routes, schemas, Problem Details, local-only security; serves web/dist)
web/                the web UI (React + TypeScript), built from openapi.yaml
```

- **The use case only knows the ports.** It doesn't know AniList or PostgreSQL exist, so it is tested with in-memory fakes, and a new data source, a cloud database or a web page doesn't change it.
- **Adapters translate errors.** httpx and psycopg errors never leave their adapter; they become `SourceUnavailable`, `RecordRefused` or `StoreUnavailable`.
- **The rules are enforced**, not just documented: import-linter fails the tests if, for example, the application imports psycopg.

Why it is built this way: [docs/adr/](docs/adr/) has one short record per decision.

**The AniList client.** 10 s timeout; retries timeouts, network errors and 5xx responses with backoff (1 s, 2 s, 4 s); never retries 4xx; on `429` waits for `Retry-After` (up to 2 minutes); spaces requests using the `X-RateLimit-Limit` header; follows `hasNextPage` and refuses partial results.

**The mapper.** Turns raw API items into `Anime` models. An item without a valid id or title is rejected; an invalid optional value becomes `NULL` with a warning. One bad item never stops the others.

**Schema** (migration [`0001_baseline.py`](src/animeverse/infrastructure/postgres/migrations/versions/0001_baseline.py)): `franchises`, `anime` and the link table `anime_franchises` (many-to-many). `anime.anilist_id` is `UNIQUE` and is the key the import upserts on. `CHECK` constraints refuse impossible values such as a score above 10.

**Idempotency.** Each table has a unique key and each insert says what to do on a conflict:

| Table | Statement | Running twice |
|---|---|---|
| `franchises` | `ON CONFLICT (name) DO UPDATE` | one row |
| `anime` | `ON CONFLICT (anilist_id) DO UPDATE` | one row per anime, values refreshed, `created_at` kept |
| `anime_franchises` | `ON CONFLICT DO NOTHING` | existing links skipped |

**Failures.** Each franchise is one transaction. If AniList or the database fails for a franchise, it is rolled back and the next one still runs. If the database refuses a single anime, only that anime is skipped (a savepoint) and it is listed in the report.

**Migrations.** Numbered Alembic migrations in plain SQL. Committed migrations never change, and anything that removes or renames goes in a separate "contract" migration after the code stops using it (expand/contract), so old and new code can run side by side during a deployment. Details in [docs/migrations.md](docs/migrations.md).

**Dates and time zones.** AniList sends dates as `{year, month, day}` with no time and no time zone, and any part can be missing. A complete date is stored as a `DATE`; an incomplete one is not guessed, but its year is kept in `start_year` / `end_year`. The only timestamps are my own `created_at` and `updated_at`, stored as `TIMESTAMPTZ`.

**Scores.** AniList's `weightedScore` (0–100) is stored as a 0–10 decimal (`85` → `8.50`).

## Limitations

- Franchise membership depends on AniList's relations. An anime without any (such as *Jujutsu Kaisen Modulo PV*, a promo video) is excluded; the report lists everything excluded.
- Imports delete an anime that no longer belongs to any franchise, unless it is on the watchlist. If it comes back later it gets a new internal id.
- Every run fetches every franchise again: one request each, about 12 seconds in total.
- Nothing is deployed: the web UI and the API run on this computer only. [ADR 0013](docs/adr/0013-how-a-public-deployment-would-work.md) describes a public, read-only version and the changes it would need.

Anime data comes from the [AniList API](https://docs.anilist.co). This project is not affiliated with AniList.
