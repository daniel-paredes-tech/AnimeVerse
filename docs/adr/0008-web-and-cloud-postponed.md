# 0008. Web application and cloud deployment postponed

- Status: Superseded by 0009 (web part; the cloud part still holds)
- Date: 2026-11-21

## Context

The goals include a web application (covers, short summaries, characters) and deployment
on AWS. Building them now would add a framework and infrastructure before the data
pipeline is finished.

## Decision

Prepare, but don't build (YAGNI):

- Ready now: the `CatalogReader` port for any web entrypoint; settings from environment
  variables only (including `POSTGRES_SSLMODE` for a managed database); a container image
  that runs `migrate` and `import`; migrations that apply automatically; CI.
- Not built until decided: a FastAPI application, Terraform, any AWS resource.

## Consequences

- Nothing is deployed and nothing costs money.
- When the web application starts, it is a new entrypoint plus new ports or use cases; the
  existing layers don't change. Characters need a new migration, a mapper change and a
  port method.
- The intended AWS shape (a managed PostgreSQL, the image run as scheduled tasks and as a
  web service, secrets injected as environment variables) will get its own ADR when it is
  decided.
