# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

- Web UI (new, in `web/`): React + Vite + TypeScript. `react-router`, `@tanstack/react-query`, and an API client generated from `openapi.yaml` (`openapi-typescript` + `openapi-fetch`). Fonts bundled from npm; no chart library (the universe map is hand-written SVG). Decided by the developer, 2026-11-23.
- Backend (exists): Python, FastAPI REST API at `/v1`, PostgreSQL. The UI talks to it **only** through the contract in `openapi.yaml`.

## Users

One primary user, the developer: an anime fan who tracks the series they watch, using AnimeVerse on their own computer. The same UI is also shown at a technical presentation for the Migracode training programme, to instructors and classmates. Both uses carry equal weight: it must be a tool worth using daily and a showcase that holds up in a demo.

## Product Purpose

AnimeVerse collects anime from several franchises (Naruto, One Piece, Dragon Ball, Attack on Titan, Demon Slayer, Jujutsu Kaisen, Yu-Gi-Oh!) from the public AniList API into a local database. The UI lets the user:

- explore that catalogue;
- see what is airing now and what is coming;
- keep a personal watchlist (status, episodes watched, a 1–10 rating, notes).

Success means the user reaches for it to explore a franchise or update their progress, and a presentation audience understands the data and the API at a glance.

## Positioning

**Franchises as universes.** AniList and MyAnimeList show anime as endless lists and pages. AnimeVerse shows each franchise as a connected world, a universe map where every anime has a place, and puts the user's watchlist inside that map. Exploring a franchise is the core idea; tracking happens within it.

## Operating Context

- Runs only on the user's computer: the API listens on 127.0.0.1 and refuses non-local hosts. There is no account, no login and no other users.
- The data is refreshed by an import job (`animeverse import`), not by the UI. Imported anime are read-only; the watchlist is the only thing the user writes.
- The database may be stopped (Docker). The UI must say so plainly and tell the user how to start it (`docker compose up -d`).
- Presentation setting: a laptop on a projector, the API's behaviour (validation errors, empty and error states) shown live.

## Capabilities and Constraints

- **API contract:** `openapi.yaml` is the only source of truth. The UI is built from it, never from the server code. If the UI needs data the contract lacks, the contract changes first, with a decision record.
- **Endpoints:**
  - list anime with filters (`q`, franchise, release status, format, start-year range, minimum score, on-watchlist, watchlist status), sort and pages (max 100 per page);
  - one anime;
  - create/replace and remove a watchlist entry;
  - the franchise list with counts.
- **Errors:** every error is RFC 9457 Problem Details. A 400 or 422 lists each invalid field with a stable `code` and a human-readable `message`, which the UI shows next to the field.
- **Watchlist rules, enforced by the server:**
  - episodes watched can't exceed the anime's episodes;
  - "completed" needs every episode watched;
  - "planning" needs zero watched.
- **Nullable data is common, and "unknown" must be shown as unknown, never as blank or zero.** Of 163 anime: 34 have no English title, 8 no score, 6 no episode count, 5 no start year, 3 no format.
- **Security (CSP):** scripts and styles only from the app itself; images only from AniList's image host (`https://s4.anilist.co`); fonts bundled; nothing else external.
- **Terminology:**
  - "format" (TV, MOVIE, OVA…), not "type";
  - "release status" (FINISHED, RELEASING, NOT_YET_RELEASED…);
  - watch statuses `planning`, `watching`, `completed`, `paused`, `dropped`;
  - a "franchise" is AnimeVerse's own grouping (AniList has no such concept).
- UI language: **English**.

## Brand Commitments

- The name is **AnimeVerse**. There is no logo or visual identity yet.
- AniList's terms: the data is free for non-commercial use, and an app may not be named just "AniList". The UI credits AniList as the data source and links each anime to its AniList page (`anilist_url`).
- Cover images belong to their rights holders and come from AniList's image server. They are shown as they are, never altered or used as decoration detached from their anime.

## Evidence on Hand

- **Real data:** 163 anime across 7 franchises (One Piece 39, Dragon Ball 38, Naruto 26, Yu-Gi-Oh! 21, Attack on Titan 20, Jujutsu Kaisen 10, Demon Slayer 9).
  - Start years run from 1982 to 2029.
  - Episode counts go up to 500.
  - Scores range 0–10 (AniList's weighted score).
  - Popularity is the number of AniList users who have the anime on their list.
- **Per anime:** titles (romaji, English, native), format, release status, episodes, start/end year, full air dates when known, score, popularity, plain-text synopsis, cover image URL, AniList link.
- **Currently:** 3 anime are airing (`RELEASING`) and 8 are not yet released.
- **Absent, so never fabricate it:**
  - characters, staff, studios, genres, trailers, banner images, airing schedule or next-episode times;
  - user reviews or ratings from other people, any social data;
  - any testimonials or usage figures for AnimeVerse itself.

## Product Principles

1. **The universe first.** Lead with the franchise worlds and how anime relate within them; lists and forms serve that.
2. **Honest data.** Show exactly what is known and say plainly what isn't; never invent, round away, or hide an unknown.
3. **The server is the authority.** Validation and errors come from the API and are shown in full, next to what caused them.
4. **Useful on a Tuesday, impressive on stage.** Every flourish must also make daily use faster or clearer, or it doesn't ship.
5. **Private and local.** Nothing leaves the computer except cover images loaded from AniList.

## Accessibility & Inclusion

WCAG 2.2 AA, confirmed by the developer on 2026-11-23:

- sufficient contrast;
- full keyboard use, including every star of the universe map;
- screen-reader names for every interactive element;
- visible focus;
- `prefers-reduced-motion` respected;
- and the map always has an equivalent list view.
