# 0011. The watchlist: user data in its own table

- Status: Accepted
- Date: 2026-11-23

## Context

The API needs one write with validation. Everything stored so far is imported from
AniList and refreshed by every import (0007), so the API must not edit it: the next
import would overwrite the change. A write needs data that belongs to the user.

## Decision

The user can keep a **watchlist entry** per anime: a status (`planning`, `watching`,
`completed`, `paused`, `dropped`), episodes watched, an optional rating from 1 to 10 and
optional notes.

- It lives in its own table, `watchlist_entries`. Its primary key is `anime_id`, a foreign
  key to `anime(id)`, so there is one entry per anime and AnimeVerse has a single local
  user. Imports never touch this table.
- The API writes it with `PUT /v1/anime/{id}/watchlist-entry` (create or replace,
  idempotent: 201 the first time, 200 after) and removes it with `DELETE` (204).
- **Rules that compare fields** live in the domain (`domain/watchlist.py`):
  - episodes watched can't exceed the anime's episodes (when known);
  - `completed` means every episode was watched (when known);
  - `planning` means none were watched.

  The database adds CHECK constraints on single fields (rating 1–10, notes length, known
  statuses) as a last line of defence. The status list is our own vocabulary, so a CHECK
  is right here, unlike AniList's free-text values in `anime`.

## Consequences

- Imported data and user data can't overwrite each other.
- `ON DELETE CASCADE`: if an anime were ever deleted, its entry would go too. Imports
  never delete (0007), so this only matters for manual cleanup.
- Several users would need a `users` table and a different key. Not needed for a local
  app (YAGNI).
- The rules depend on `anime.episodes`, which an import can change. An entry that was
  valid can become invalid after a refresh (rare). It stays stored, and the rules are
  applied again on the next write.
