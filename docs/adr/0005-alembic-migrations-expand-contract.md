# 0005. Alembic migrations with expand/contract

- Status: Accepted
- Date: 2026-11-21

## Context

The schema lived in `db/schema.sql`, which PostgreSQL ran only on an empty data volume.
When `start_year` and `end_year` were added, the change had to be applied by hand with
`ALTER TABLE`; any other copy of the database would have kept the old schema, and the only
alternative was deleting all data. A cloud deployment needs schema changes that apply
automatically and safely while old and new code run side by side.

## Decision

- Every schema change is a numbered Alembic migration (`0001`, `0002`, …) written in plain
  SQL, applied with `animeverse migrate`. `0001_baseline` is the former `db/schema.sql`,
  which was removed.
- Committed migrations are immutable (checked by a SHA-256 lock file and a test).
- Expand/contract: normal migrations only add; removing, renaming or tightening goes in a
  separate `*_contract_*` migration once no code uses the old shape (checked by a test).
- Migrations go forward in production; `downgrade()` is for local development.

Alembic was chosen over dbmate and Flyway because it is the standard in Python, runs from
the same settings as the application, and suits the planned FastAPI web application.

## Consequences

- The test database, a developer's database and a future cloud database are all built by
  the same migrations.
- Changing the schema takes two steps (and two releases) when something is removed.
- Adds Alembic and SQLAlchemy as dependencies. The existing local database was marked as
  `0001` with `alembic stamp 0001`; its `start_year`/`end_year` columns sit at the end of
  the table instead of after `aired_to`, which changes nothing because queries name columns.

See [docs/migrations.md](../migrations.md).
