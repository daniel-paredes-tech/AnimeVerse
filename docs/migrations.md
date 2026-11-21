# Database migrations

The database schema is changed **only** by migrations: numbered Python files in
[`src/animeverse/infrastructure/postgres/migrations/versions/`](../src/animeverse/infrastructure/postgres/migrations/versions/),
run by [Alembic](https://alembic.sqlalchemy.org/). Alembic records the applied
revision in the `alembic_version` table, so it only applies what a database is missing.

```bash
animeverse migrate                   # apply every pending migration (safe to run any time)
alembic current                      # which revision this database is at
alembic history                      # every migration, in order
alembic upgrade head --sql           # print the SQL without running it (to review)
```

## The rules

These are checked by `tests/test_migrations.py`, so breaking one fails the tests.

1. **Numbered, in one line.** `0001_baseline.py`, `0002_…`, each pointing to the previous one.
2. **Immutable.** A committed migration is never edited or deleted, even to fix a typo:
   databases that already ran it would never see the change. Write a new migration instead.
   `migrations.lock` holds the SHA-256 of every committed migration.
3. **Expand before contract.** A normal migration only *adds*: tables, nullable columns,
   columns with a default, indexes, relaxed constraints. Anything that removes, renames
   or tightens (`DROP`, `RENAME`, `ALTER … TYPE`, `SET NOT NULL`, `TRUNCATE`, `DELETE`)
   goes in a separate migration whose file name contains `contract`.
4. **Plain SQL.** Migrations use `op.execute("…")`; AnimeVerse has no ORM.
5. **Forward only in production.** `downgrade()` exists for local development; a mistake
   in production is fixed with a new migration.

## Adding a migration

```bash
alembic revision --rev-id 0002 -m "add anime season"   # creates versions/0002_add_anime_season.py
# write the SQL in upgrade() (and downgrade() for local use)
animeverse migrate                                      # apply it locally
python -m pytest                                        # the test database is rebuilt from all migrations
python tests/test_migrations.py                         # record the new file in migrations.lock
```

Commit the migration, the code that uses it and the lock line together.

## Why expand/contract

When the application runs on more than one machine (for example on AWS), a deployment
is not instantaneous: for a while the **old and the new version of the code run at the
same time against the same database**. A migration that renames or drops a column breaks
the old code during that window. Splitting the change in two avoids it:

| Step | Migration | Code |
|---|---|---|
| 1. Expand | add the new shape, keep the old one | old code still works |
| 2. Deploy | — | new code writes both shapes (or reads the new one with a fallback) |
| 3. Migrate data | copy old → new (a normal, additive migration, or a script) | — |
| 4. Switch | — | new code uses only the new shape |
| 5. Contract | `…_contract_….py` removes the old shape | nothing uses it any more |

Every step can be deployed, tested and reverted on its own.

### Example: renaming `anime.type` to `anime.format`

```text
0002_add_anime_format.py           ALTER TABLE anime ADD COLUMN format TEXT;
                                   UPDATE anime SET format = type;
(code)                             write both columns; read format, fall back to type
(code, next release)               read and write only format
0003_contract_drop_anime_type.py   ALTER TABLE anime DROP COLUMN type;
```

A real example that was already additive: `start_year` and `end_year` were added as
nullable columns, so the old code kept working while the new code filled them in.
