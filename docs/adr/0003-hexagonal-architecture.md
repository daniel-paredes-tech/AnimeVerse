# 0003. Hexagonal architecture (ports and adapters)

- Status: Accepted
- Date: 2026-11-21

## Context

The first version was a flat package where the import service imported the AniList client
and the PostgreSQL driver directly, and caught their errors. The plans are a web
application, a database in the cloud and scheduled imports. Each of those would have
meant editing the import logic, and tests needed `monkeypatch` to simulate failures.

## Decision

Four layers, with dependencies pointing inwards:

```
entrypoints  ->  infrastructure  ->  application  ->  domain
(CLI, web)       (AniList,           (use cases,       (models,
                  PostgreSQL)         ports)            rules)
```

- **domain**: `Anime`, `Franchise`, `MembershipRule`. Imports nothing of ours or anyone's.
- **application**: the `ImportCatalog` use case and the ports it needs (`AnimeSource`,
  `CatalogStore`, `CatalogReader`), as `typing.Protocol`s, with the errors each may raise.
- **infrastructure**: adapters that implement the ports and translate library errors
  (httpx, psycopg) into the ports' errors.
- **entrypoints**: the `animeverse` command (the composition root, the only place that
  picks concrete adapters) and the local page.

The rules are enforced by import-linter (`[tool.importlinter]` in `pyproject.toml`), run
as a test, and the ports are type-checked by mypy in strict mode.

## Consequences

- The use case is tested with in-memory fakes, without network or database. Contract tests
  run the same checks against the fake and the real PostgreSQL store, so the fake is trusted.
- A web application is a new entrypoint using `CatalogReader`; a cloud database is the same
  adapter with different settings; a new data source is a new adapter.
- More files and one level of indirection than a flat script. Accepted because the project
  is meant to grow; the layers stay thin (no generic frameworks, no registries until a
  second implementation exists).
