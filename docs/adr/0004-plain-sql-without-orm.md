# 0004. Plain SQL, no ORM

- Status: Accepted
- Date: 2026-11-16 (recorded 2026-11-21)

## Context

The application reads and writes three tables, and its key operations are PostgreSQL
upserts (`INSERT … ON CONFLICT`) whose exact SQL matters for idempotency.

## Decision

Write SQL by hand, with parameterized queries, in one module
(`infrastructure/postgres/repository.py`), using psycopg 3. No ORM.

SQLAlchemy is installed only because Alembic needs it to run migrations (0005); the
application code does not use it.

## Consequences

- The SQL that runs is the SQL in the file: easy to read, explain and tune.
- Rows are mapped to domain objects by hand; with more tables that grows. If it ever
  becomes a burden, SQLAlchemy Core is already installed and could be adopted inside the
  PostgreSQL adapter without touching other layers.
