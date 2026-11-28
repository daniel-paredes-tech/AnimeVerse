# 0013. How a public deployment would work

- Status: Accepted (nothing is built or deployed yet)
- Date: 2026-11-28
- Builds on: [0008](0008-web-and-cloud-postponed.md) (the cloud part) and [0009](0009-api-and-web-app-now.md)

## Context

AnimeVerse runs only on this computer, and on purpose (0009): the server binds to
127.0.0.1, refuses any `Host` header that isn't local, and lets anyone who reaches it edit
the watchlist. The goal is to be able to publish it on AWS later without a redesign.

0008 already prepared most of it: settings come only from environment variables
(including `POSTGRES_SSLMODE` for a managed database), logs go to stdout, the container
image runs every command, and migrations apply automatically and allow old and new code to
run side by side (0005).

This ADR records what a public version would be, and the code changes it would still need,
so nobody has to rediscover them. It doesn't choose AWS services: that is decided when the
deployment is built.

## Decision

**What a public version is.** A read-only catalogue for visitors:

- Visitors can browse the anime and franchises imported from AniList. Nothing can be
  written.
- The watchlist doesn't appear at all: no entry on an anime, no watchlist filters, no write
  routes. It is personal data, and hiding it means nothing is exposed by accident.
- The watchlist stays in the local database and is edited only in the local version, as
  today. The cloud database holds only the imported catalogue.

**What it runs on.** Any platform that offers these four pieces:

| Piece | What it does |
|---|---|
| A managed PostgreSQL | The catalogue. Connected with `POSTGRES_SSLMODE=verify-full`. |
| A web service | Runs the image with `animeverse serve`, behind the platform's HTTPS. |
| A scheduled task | Runs the same image with `animeverse import`, rarely (for example once a day), because AniList's terms forbid mass collection. |
| A one-off task per release | Runs `animeverse migrate` before the new web version starts. |

The database password comes from the platform's secrets store as an environment variable,
never from a file in the image.

**The code changes it needs.** All are configuration of the entrypoints; the domain and
application layers don't change.

1. **One switch for the mode.** A setting such as `SERVE_MODE`, `local` by default. `public`
   turns on items 2 to 4 together. One switch, not three, so no combination can be half
   public: for example, listening on every interface while the watchlist is still writable.
2. **Listen on every interface** (`0.0.0.0`) in public mode, on the port the platform
   gives. Today `server.py` always binds to 127.0.0.1.
3. **Allowed hosts from a setting** (the public domain names), required in public mode.
   Today `security.py` accepts only `localhost`, `127.0.0.1` and `::1`.
4. **No watchlist in public mode.** First in the contract (0010): how a read-only server
   describes the missing watchlist fields, filters and routes. Then the server, then the UI,
   which must not show the watchlist form.
5. **A health route** in the contract and the server, so the platform can check the web
   service is alive and restart it if not. It must not query the database: if the database
   is down, restarting the web service doesn't help, and it would restart in a loop.
6. **A complete image.** Today the image holds only the Python package. It also needs
   `openapi.yaml` (without it `animeverse serve` refuses to start) and the built web UI
   (`web/dist`), built in an extra Node.js stage of the `Dockerfile`, so Node.js isn't in the
   final image.

## Consequences

- Publishing needs no redesign: six changes in the entrypoints, the contract, the UI and
  the `Dockerfile`, each small and testable on its own.
- The local version keeps working exactly as today, because `local` is the default.
- The public version can't leak or lose the watchlist: it has no watchlist.
- There are two databases: the local one (catalogue and watchlist) and the cloud one
  (catalogue only). Each runs its own imports and migrations.
- Each request still opens its own database connection. That is fine for a small site; a
  connection pool is the first change if traffic grows.
- Until this is built, nothing is deployed and nothing costs money (as 0008 decided).
