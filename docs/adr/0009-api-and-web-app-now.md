# 0009. API and web application now; cloud still postponed

- Status: Accepted
- Date: 2026-11-23
- Supersedes: [0008](0008-web-and-cloud-postponed.md) (the web part; its cloud part is kept)

## Context

0008 postponed the web application and FastAPI until the data pipeline was finished. The
pipeline is finished (import, migrations, CI), and this week's Migracode brief asks for a
REST API described by an OpenAPI contract, and a web UI with a dashboard that consumes it.

0008 also prepared for this moment: a new entrypoint plus new ports, with the existing
layers left unchanged.

## Decision

- Build a versioned REST API (`/v1`) with **FastAPI**, as a new entrypoint
  (`entrypoints/api/`). FastAPI was already the framework named in the stack. It brings
  Pydantic for request validation, and **uvicorn** runs it.
- Build the web UI as a separate app in `web/` (**React + Vite + TypeScript**). It talks
  to the API only through the contract (see 0010).
- Everything stays **local**: the server binds to 127.0.0.1 and accepts only local
  `Host` headers, keeping the DNS-rebinding protection of the old page.
- The old read-only page (`entrypoints/web/`, standard library, no JavaScript) is
  replaced by the new UI. It is removed in a separate, final commit once the new UI works
  (expand/contract).
- The new UI's Content-Security-Policy allows scripts and styles from the app itself and
  images from AniList's image server (cover art), and nothing else. Fonts are bundled,
  not loaded from a CDN.

Cloud deployment (Terraform, any AWS resource) stays postponed, as 0008 decided.

## Consequences

- New runtime dependencies: `fastapi`, `uvicorn`. New toolchain: Node.js for the UI and
  for Redocly. The layer rules forbid FastAPI, Pydantic, Starlette and uvicorn in the
  domain and application layers.
- `animeverse serve` now starts the API (and serves the built UI), not the old page.
- Two languages in one repository: Python for the backend and pipeline, TypeScript for
  the UI. CI checks both.
