# Architecture Decision Records

Short notes on why AnimeVerse is built the way it is. One file per decision; a decision
is never edited after it is accepted. A new decision that replaces an old one says so,
and the old one is marked "Superseded".

| # | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-anilist-as-data-source.md) | AniList as the data source | Accepted |
| [0003](0003-hexagonal-architecture.md) | Hexagonal architecture (ports and adapters) | Accepted |
| [0004](0004-plain-sql-without-orm.md) | Plain SQL, no ORM | Accepted |
| [0005](0005-alembic-migrations-expand-contract.md) | Alembic migrations with expand/contract | Accepted |
| [0006](0006-franchise-membership-by-title.md) | Franchise membership decided by title | Accepted |
| [0007](0007-idempotent-import-never-delete.md) | Idempotent import that never deletes | Accepted |
| [0008](0008-web-and-cloud-postponed.md) | Web application and cloud deployment postponed | Accepted |

Template for a new one:

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What problem or force made a decision necessary.

## Decision
What we do.

## Consequences
What becomes easier, what becomes harder, what we accept.
```
