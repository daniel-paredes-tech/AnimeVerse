# AnimeVerse: OpenAPI contract → FastAPI → React dashboard

## Context

This week's Migracode brief asks for three things, in this order:
1. **Contract first.** A hand-written `openapi.yaml` with a list (filters + pagination), a get-one, one validated write, a single error shape and explicit nullable fields. It is linted with `npx @redocly/cli lint openapi.yaml` and committed **before any server code**. The server must be proven to match it.
2. **A real REST API** that follows industry practice: correct status codes, consistent errors, versioning.
3. **A creative UI/dashboard** built *only* from `openapi.yaml` (the UI agent never sees the server code). It has a detail view, a form that shows the API's validation errors, and empty and error states. If the UI needs something the contract lacks, the contract changes first and gets an ADR.

This reverses earlier decisions: the project guidelines and ADR 0008 said "no website, FastAPI postponed", and the current local page forbids JavaScript and external resources. The developer has now asked for the work, so those decisions get superseded on the record.

**Decided with the developer (2026-11-23):**
- The write is a **watchlist entry** (status, episodes watched, rating, notes), stored in a new table. Approving this design counts as the schema approval the project guidelines require.
- The UI is **React + Vite + TypeScript**. Its API types are generated from `openapi.yaml` (openapi-typescript + openapi-fetch), so the build fails if the UI drifts from the contract.
- The backend is **FastAPI** (already the project's planned framework). It stays local only, with no cloud.

## Approaches considered

- **The write.** Chosen: the watchlist entry, which is personal data and has rules that compare fields (episodes watched vs total episodes). Rejected: reviews (validation only checks lengths and ranges) and "add a franchise" (it would move the franchise list from config into the database and make the API trigger AniList calls).
- **The UI.** Chosen: React + TypeScript with types generated from the contract. Rejected: React with plain JS (nothing catches drift from the contract) and vanilla HTML/JS (routing and state written by hand, and no contract check).
- **How code follows the contract.** Chosen: a hand-written spec plus contract tests. Rejected: FastAPI's code-first generated schema, because the brief asks for the contract to be written before the code.

## Approach: the contract is the source of truth

`openapi.yaml` (OpenAPI **3.1**) lives at the repo root. FastAPI's auto-generated schema is turned off (`openapi_url=None`), so there is only one contract. The hand-written file is served at `GET /v1/openapi.yaml`. Four checks keep code and contract in line:
1. **Redocly lint**: `redocly.yaml` extends `recommended`. It runs locally and in CI.
2. **Schemathesis** (pytest integration). It loads *the yaml file* and runs generated requests against the in-process ASGI app on the test DB. It checks that every status code, content type and response body conforms to the spec, and that invalid input is rejected.
3. **Route parity test.** The set of (method, path) pairs in the FastAPI app must equal the set in the spec.
4. **UI side.** `npm run gen:api` regenerates `web/src/api/schema.d.ts`. CI fails if the regenerated file differs from the committed one, and `tsc` fails if the UI uses fields the contract doesn't have.

## The contract (v1)

All paths are under `/v1`. Field names are snake_case, matching the DB and Python. Every field is always present (`required`), and the ones that can be null use `type: [X, "null"]`, so "unknown" (`null`) is always distinct from "missing".

| Method & path | Purpose | Success | Errors |
|---|---|---|---|
| `GET /v1/anime` | List with filters, sort, pagination | 200 | 400, 503 |
| `GET /v1/anime/{anime_id}` | Detail: franchises + watchlist entry (nullable) | 200 | 400, 404, 503 |
| `PUT /v1/anime/{anime_id}/watchlist-entry` | Create or replace your entry (idempotent) | 201 created / 200 replaced | 400, 404, 415, 422, 503 |
| `DELETE /v1/anime/{anime_id}/watchlist-entry` | Remove it | 204 | 404, 503 |
| `GET /v1/franchises` | Franchises + anime count (filter options, dashboard) | 200 | 503 |
| `GET /v1/openapi.yaml` | The contract itself | 200 | none |

- **List query params:** `q` (title, case-insensitive, matches romaji/English/native), `franchise` (id), `status`, `format`, `year_from`/`year_to` (start_year), `min_score`, `watchlist_status` (or `on_watchlist=true`), `sort` ∈ `popularity|score|start_year|title`, each optionally prefixed with `-` for descending (default `-popularity`), `page` ≥1, `page_size` 1–100 (default 24). Unknown values return 400.
- **List response:** `{ "data": [AnimeSummary], "meta": {page, page_size, total_items, total_pages}, "links": {self, next|null, prev|null} }`. AnimeSummary leaves out `synopsis`; AnimeDetail adds `synopsis`, `franchises[]` and `watchlist_entry|null`.
- **Write body:** `{status: planning|watching|completed|paused|dropped, episodes_watched: int ≥0, rating: int 1–10 | null, notes: string ≤1000 | null}`. `additionalProperties: false`.
- **Validation rules (422):** `episodes_watched ≤ anime.episodes` when episodes is known. `completed` requires `episodes_watched == episodes` when known. `planning` requires `episodes_watched == 0`. The rules that compare fields live in the domain (see below), and the spec documents them in `description` plus an example.
- **Error shape: RFC 9457 Problem Details** (`application/problem+json`): `type` (URI under `https://animeverse.local/problems/…`), `title`, `status`, `detail`, `instance`, plus `errors: [{field, code, message}]` for 400/422. Status codes:
  - 400: malformed JSON or bad query/path parameters (syntax).
  - 422: the body is well-formed but breaks the rules (semantics).
  - 404: unknown anime, and also unknown routes.
  - 415: the body is not `application/json`. This also blocks cross-site HTML form posts.
  - 503: the database is unavailable (`StoreUnavailable`).
  - 500: generic, with no internals leaked.
- **Not in v1 (YAGNI, listed as possible improvements):** ETag/If-Match concurrency, auth (single local user), cursor pagination (~160 rows).

## Architecture (hexagonal, existing rules kept)

- `domain/watchlist.py`: `WatchStatus` (StrEnum), a frozen `WatchlistEntry` dataclass, and `validate_entry(entry, episodes) -> list[FieldError]`. It's pure, so it's easy to unit-test.
- `domain/models.py`: read models `AnimeSummary` / `AnimeDetail` (or extend `Anime` with `id`), plus `FranchiseSummary`. Existing `Anime`/`Franchise` stay unchanged for the importer.
- `application/ports.py`: new `CatalogQuery` Protocol (`list_anime(AnimeFilters, Sort, PageRequest) -> Page[AnimeSummary]`, `get_anime(id) -> AnimeDetail | None`, `list_franchises()`) and `WatchlistStore` (`save(anime_id, entry) -> created: bool`, `delete(anime_id) -> bool`). New errors: `AnimeNotFound`, `InvalidWatchlistEntry(errors)`. Existing `CatalogReader` stays until the old page is removed.
- `application/watchlist.py`: the use cases `save_watchlist_entry` (load anime → 404, validate → 422, save) and `remove_watchlist_entry`.
- `infrastructure/postgres/catalog_queries.py`: parameterized SQL, built dynamically with `psycopg.sql` for WHERE/ORDER BY. ORDER BY uses a whitelist mapping and adds a stable tiebreaker `id`. It returns one page plus `count(*) OVER ()`.
- `infrastructure/postgres/watchlist_store.py`: `INSERT … ON CONFLICT (anime_id) DO UPDATE … RETURNING (xmax = 0)` to tell created from replaced (the same trick the existing upsert uses, see `repository.py:upsert_anime`). psycopg errors become port errors, as in `store.py`.
- **Migration `0002_watchlist_entries.py`** (expand-only, plain SQL): `watchlist_entries(anime_id INTEGER PRIMARY KEY REFERENCES anime(id) ON DELETE CASCADE, status TEXT NOT NULL CHECK (status IN (…)), episodes_watched INTEGER NOT NULL DEFAULT 0 CHECK (≥0), rating SMALLINT CHECK (1–10), notes TEXT CHECK (char_length ≤1000), created_at, updated_at)`. Status gets a CHECK because it's our own vocabulary (unlike AniList's free text). There are no extra indexes: ~160 rows, which the comment explains. Record it with `python tests/test_migrations.py`.
- `entrypoints/api/`:
  - `app.py`: `create_app(catalog, watchlist, settings)`, the app factory with injected ports, like `make_handler`.
  - `routes.py`, `schemas.py`: Pydantic DTOs, separate from domain models.
  - `problems.py`: exception handlers → problem+json, including FastAPI's `RequestValidationError` → 400/422 split by location.
  - Security middleware: `TrustedHostMiddleware` for localhost only (keeps the DNS-rebinding protection of `server.py:is_local_host`), plus a CSP. Binds to 127.0.0.1.
  - In production mode it serves the built UI from `web/dist` at `/`.
- `cli.py`: `animeverse serve` now runs uvicorn with `create_app` (`--port`, `--open` kept). The old stdlib page is removed in a separate final commit (expand/contract).
- **import-linter:** add `fastapi`, `pydantic`, `starlette`, `uvicorn` to the "domain and application never import…" forbidden list.
- **New dependencies (exact pins, justified in the ADR):** `fastapi`, `uvicorn` (runtime); `schemathesis` (dev). Verify the current versions and Python 3.14 support before pinning. Redocly runs through `npx`, so it adds no Python dependency.

## Web UI (`web/`, built only from openapi.yaml)

- Vite + React + TS, `react-router`, `openapi-typescript` + `openapi-fetch`. The Vite dev server proxies `/v1` → `127.0.0.1:8000`, so no CORS is needed. Fonts are self-hosted from npm. The only external resource is the AniList cover images (`img-src 'self' https://s4.anilist.co`; check the host against the stored `image_url` values first).
- Design direction comes from the **impeccable** skill (`/impeccable init` writes a `DESIGN.md`) before the screens are built. Views:
  - **Dashboard** `/`: "Continue watching" (watchlist entries with progress rings), franchise "universe" cards (cover mosaic, count, average score), "Airing now / upcoming" (status `RELEASING` / `NOT_YET_RELEASED`, the closest thing to live scores in our data), a release timeline by year across franchises, and score vs popularity.
  - **Browse** `/anime`: filters and sort kept in the URL query string, paginated cards.
  - **Detail** `/anime/:id`: cover, synopsis, franchises, and the **watchlist form**, which maps each 422 `errors[].field` onto its input and shows other problem types in a banner.
  - **States everywhere:** loading skeletons; empty ("no anime match these filters" + clear filters; "your watchlist is empty"); error (renders the problem `title`/`detail`, with a retry; a 503 explains "start the database: `docker compose up -d`").
- **Built by a subagent given only:** `openapi.yaml`, `DESIGN.md`, and this brief, scoped to `web/` and told not to read `src/`. If it needs data the contract lacks (likely: dashboard aggregates such as a `GET /v1/stats` endpoint), it stops and reports. Then the contract change, an ADR, the server change and contract tests come first, and the UI after.
- **Tests:** `tsc --noEmit`, plus Vitest + Testing Library for the form's error mapping and the empty/error states (fetch mocked with examples taken from the spec).
- Note: a live airing countdown would need AniList's `nextAiringEpisode`, which we don't import. It's out of scope unless asked for, and would be a pipeline change + migration + contract change.

## Order of work (each step is its own commit on a feature branch, explained to the developer before it's written)

1. **Records:**
   - Design doc `docs/superpowers/specs/2026-11-23-api-and-webapp-design.md`.
   - ADR 0009 "API and web app now; supersedes 0008 (cloud still postponed)".
   - ADR 0010 "Contract-first OpenAPI, Problem Details, contract testing".
   - ADR 0011 "Watchlist: user data in its own table".
   - Update the project guidelines (stack, layout, local page rules → new UI + CSP rules, commands).
2. **`openapi.yaml` + `redocly.yaml`** → `npx @redocly/cli lint openapi.yaml` clean → commit (the assignment's milestone).
3. **Migration 0002** + lock file + migration tests.
4. **Domain + application** (TDD): `validate_entry` tests, use cases against the fakes in `tests/fakes.py`.
5. **Postgres adapters** + contract tests in `tests/test_store_contract.py` style (fake and Postgres run the same checks).
6. **FastAPI entrypoint**: Schemathesis + route parity + focused tests (pagination links, 404/415/422 problem bodies, 503 with a store that fails). Swap `serve`.
7. **CI**: a Node step for Redocly lint; the web job runs `npm ci`, `gen:api` up-to-date check, `tsc`, vitest, build. The Dockerfile builds the UI in a node stage (optional; keep if simple).
8. **Design** (impeccable → `DESIGN.md`), then **the UI subagent** (contract-only), with contract additions through ADRs.
9. **Contract step:** remove the old stdlib page (`entrypoints/web/`, its tests, `CatalogReader` if unused), and update the README.


## Verification

- `npx @redocly/cli lint openapi.yaml` → no errors.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/lint-imports && .venv/bin/python -m pytest` (DB running; check pytest's own exit code). This includes Schemathesis and route parity against `openapi.yaml`.
- `cd web && npm run gen:api && git diff --exit-code src/api/schema.d.ts && npm run typecheck && npm test && npm run build`.
- Manual end to end: `docker compose up -d`, `animeverse import`, `animeverse serve`, then `curl` the list/detail/PUT (valid, 422, 415, 404) and inspect the problem+json. Run the UI (`npm run dev`) and use the **run** skill / browser to check the dashboard, filters and pagination, the detail page, the form showing a 422 on episodes > total, empty filters, and the 503 state with the DB stopped.
