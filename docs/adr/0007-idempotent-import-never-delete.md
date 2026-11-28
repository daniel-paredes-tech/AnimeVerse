# 0007. Idempotent import that never deletes

- Status: Accepted, amended by 0012 (anime left in no franchise are deleted, unless in the watchlist)
- Date: 2026-11-16 (recorded 2026-11-21)

## Context

The import must be safe to run any number of times (the assignment's requirement, and
necessary for scheduled imports). Data from the source can also disappear or fail.

## Decision

- Every table has a natural unique key and every write is an upsert: franchises by `name`,
  anime by `anilist_id`, links by `(franchise_id, anime_id)`.
- `anilist_id` is the external identity; `id` is an internal one that no other system
  depends on. `mal_id` is reference data and deliberately not unique.
- One transaction per franchise; one savepoint per anime, so a refused anime is skipped
  and reported without losing the rest.
- Imports insert and refresh, never delete.

## Consequences

- Running the import twice gives "0 new"; a failed franchise leaves the database as it was.
- If AniList is down, the stored data stays available to read.
- An anime that disappears from AniList, or stops matching its franchise, stays in the
  database. Removing stale data would need its own, explicit decision.
