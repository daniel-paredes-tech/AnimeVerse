# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AnimeVerse

## 1. Project Overview

AnimeVerse is an educational software development project created as part of the Migracode training program.

The goal is to build a local anime information platform using public APIs, Python and PostgreSQL.

The application will initially collect anime-related information from the AniList API and store it in a PostgreSQL database.

The long-term vision is to create a website where users can explore anime, search for characters, browse information and discover different anime universes, including Naruto, Jujutsu Kaisen, Yu-Gi-Oh! and others.

This is primarily a learning project. Code quality, understanding and good engineering practices are more important than development speed.

## 2. Main Objective

Build a reliable data ingestion pipeline that:

1. Connects to a public API.
2. Retrieves data using an API client.
3. Parses and normalizes the response.
4. Stores the information in PostgreSQL.
5. Prevents duplicate records when the import runs multiple times.
6. Handles network errors, invalid records and API rate limits.

Everything must run locally.


## 3. Technology Stack

Use the following technologies:

- Programming language: Python.
- External API: AniList GraphQL API. (Jikan was the original choice; it was abandoned on 2026-11-16 because its API was down for everyone.)
- HTTP client: HTTPX.
- Backend framework: FastAPI.
- Database: PostgreSQL.
- Database execution: Docker Compose.
- Database access: SQL and a dedicated repository layer.
- Frontend: HTML, CSS and vanilla JavaScript.
- Testing: Pytest.
- Version control: Git and GitHub.

Avoid introducing additional frameworks or dependencies without explaining why they are necessary.

Do not introduce AWS, Kubernetes, Terraform or cloud deployment in this project.

## 4. Required Architecture

Keep the application modular and separate responsibilities.

### API Client

Responsible for communicating with the external API.

Requirements:

- Implement request timeouts.
- Handle HTTP errors.
- Implement controlled retries for temporary failures.
- Respect the API rate limits.
- Handle pagination.
- Avoid unnecessary API requests.
- Never assume an endpoint or response field exists without verifying the documentation.

### Parser

Responsible for converting external API responses into our own clean data models.

Requirements:

- Validate incoming data.
- Normalize field formats.
- Handle missing or null values.
- Handle inconsistent data.
- Normalize dates and timestamps where applicable.
- Prevent one malformed record from crashing the entire import.
- Separate external API models from internal database models.

### Repository

Responsible for all database operations.

Requirements:

- Keep SQL queries and persistence logic in this layer.
- Implement insert and update operations.
- Use parameterized queries.
- Implement idempotent imports.
- Use unique constraints and appropriate upsert operations.
- Handle database errors correctly.

### Database

Use PostgreSQL running inside a Docker container.

Requirements:

- Provide docker-compose.yml.
- Provide a database schema.
- Use appropriate primary keys and foreign keys.
- Use appropriate data types.
- Create indexes where justified.
- Use persistent Docker volumes.
- Configure a database health check.

Running the import multiple times must not create duplicate records.

## 5. API Documentation and Data Validation

The selected API is AniList (GraphQL, no API key needed for public data):

- Endpoint: `POST https://graphql.anilist.co`, with a JSON body containing `query` and `variables`.
- Documentation: https://docs.anilist.co (source: https://github.com/AniList/docs). GraphQL introspection can be used to verify field types and enum values.

Verified AniList rules (2026-11-16):

- Rate limit: normally 90 requests per minute, but the docs say the API is in a "degraded state" limited to 30 per minute. Read the `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers rather than hard-coding a number. Exceeding the limit returns `429` with `Retry-After` (seconds) and `X-RateLimit-Reset`, plus a 1-minute timeout. A separate burst limiter also exists.
- Pagination: `Page(page, perPage) { pageInfo { hasNextPage } }`. Rely only on `hasNextPage`: the docs say `total` and `lastPage` are currently inaccurate.
- Terms of use: free for non-commercial use. Mass data collection ("hoarding") is prohibited (the docs say they are lenient with educational projects). An app may not be named just "AniList".
- `averageScore` is deprecated; use `weightedScore` (0–100).
- Search is loose: e.g. "demon slayer" also returned an unrelated anime, so imports need a rule for which results belong to a franchise.

Before writing the API client:

1. Explore the API manually using a browser or curl.
2. Read the official documentation.
3. Inspect actual JSON responses.
4. Identify available fields.
5. Identify pagination behavior.
6. Identify rate limits.
7. Confirm which information is suitable for our database.

Never invent endpoints, parameters, response fields or API capabilities.

If documentation and actual API responses differ, report the discrepancy before implementing a solution.

Treat external API data as untrusted input.

## 6. Database and Idempotency

Design the database based on the actual data available from the API.

Do not create unnecessary tables or relationships.

Before implementing the schema:

1. Inspect the API response.
2. Propose a data model.
3. Explain the relationships.
4. Explain the primary and unique keys.
5. Wait for the developer's approval.

Use the external API identifier as a reference for identifying imported records whenever appropriate. For anime this is AniList's `id`, stored as `anime.anilist_id` (the upsert key). `anime.mal_id` is optional reference data and deliberately not unique.

Use PostgreSQL constraints and ON CONFLICT operations where appropriate.

An import must be safe to execute repeatedly.

## 7. Security and Environment Configuration

- Store credentials and configuration in environment variables.
- Use .env for local configuration.
- Include .env.example with placeholder values.
- Add .env to .gitignore before the first commit.
- Never commit passwords, credentials or API secrets.
- Do not expose database credentials in application logs.

## 8. Testing Requirements

Use Pytest.

Create tests for:

- API client responses.
- API timeouts and temporary failures.
- Parser validation.
- Missing and malformed fields.
- Repository database operations.
- Duplicate prevention.
- Repeated imports.

Use mocks for external API tests where appropriate.

Do not depend on the availability of the external API for every automated test.

## 9. Development Methodology

This is an educational project.

Claude Code must act as both a programming assistant and a technical tutor.

Follow these rules:

1. Never generate the entire application in one operation.
2. Work incrementally, one component at a time.
3. Explain the purpose of each file before creating it.
4. Explain the reasoning behind important technical decisions.
5. Present the proposed implementation before making significant changes.
6. Ask questions when an important architectural decision requires developer input.
7. Do not hide errors or silently ignore failures.
8. Prefer simple and maintainable solutions over unnecessary complexity.
9. Do not introduce dependencies without justification.
10. Do not assume the developer understands code that has just been generated.

When implementing a component:

- Explain its responsibility.
- Explain how it interacts with other components.
- Implement only the agreed functionality.
- Run the relevant tests.
- Explain the results.
- Identify possible improvements.

If a task can be used as a learning opportunity, guide the developer through the reasoning instead of immediately providing a complete solution.


## 10. Git and GitHub

- Use meaningful commit messages.
- Keep the repository organized.
- Never commit .env files.
- Include a useful README.md.
- Keep the project reproducible on another local machine.
- Do not commit generated files, unnecessary dependencies or local database credentials.
- Author every commit as the developer. Do not add a `Co-Authored-By` trailer or any other Claude Code attribution to commit messages or pull requests.

## 11. Important Final Rule

The priority is to build a project that the developer fully understands and can explain during a technical presentation.

Do not optimize for generating the largest amount of code.

Optimize for learning, correctness, maintainability and understanding.

## 12. Commands

Database: PostgreSQL 18 in Docker. Settings come from `.env`, which you create by copying `.env.example`.

```bash
docker compose up -d       # start the database
docker compose ps          # status: wait for "healthy"
docker compose down        # stop; the data stays in the pgdata volume
docker compose down -v     # stop and DELETE all data (needed to re-apply schema changes)
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'   # SQL shell, no password typed
```

- `db/schema.sql` only runs when the data volume is empty (first start). Editing it has no effect on an existing database until the volume is reset or the change is applied by hand.
- The host port is `POSTGRES_PORT` in `.env` (default 5432). On the developer's machine it is 5433, because another project's container already uses 5432.

Python: 3.14 (installed with Homebrew; the macOS system Python 3.9 is too old). Dependencies are pinned in `requirements.txt` (app) and `requirements-dev.txt` (app + pytest).

```bash
/opt/homebrew/bin/python3.14 -m venv .venv            # create the virtual environment (once)
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest                            # all tests (the database must be running)
.venv/bin/python -m pytest tests/test_repository.py   # one file
.venv/bin/python -m pytest tests/test_repository.py::test_link_twice_creates_one_link   # one test
```

- Database tests never use the main database. `tests/conftest.py` creates `<POSTGRES_DB>_test` in the same container, rebuilds it from `db/schema.sql` at the start of every run, and rolls back each test's changes.
- Repository functions never commit; the caller controls transactions.
- There are no import or web app commands yet. Add them here when they exist.
