# 0010. Contract-first OpenAPI, Problem Details errors, contract tests

- Status: Accepted
- Date: 2026-11-23

## Context

The API has more than one possible consumer: our UI today, maybe other programs later.
They need a stable, explicit description of what the API offers (design principle 7).
FastAPI can generate an OpenAPI document from the code, but then the code defines the
contract and any code change silently changes it. The brief asks for the opposite: write
the contract first, then make the code match it.

## Decision

1. **`openapi.yaml` at the repository root is the contract** (OpenAPI 3.1). It is written
   by hand and changed before the code. FastAPI's generated schema is turned off
   (`openapi_url=None`); the API serves the hand-written file at `/v1/openapi.yaml`.
2. **Errors use RFC 9457 Problem Details** (`application/problem+json`): `type`, `title`,
   `status`, `detail`, `instance`, plus an `errors` list (`field`, `code`, `message`) for
   validation problems. One shape for every error, documented once and reused everywhere.
3. **Status codes:**
   - 400: a request that is malformed (bad JSON, a bad query or path parameter).
   - 422: a well-formed body that breaks a rule.
   - 404: a resource that does not exist.
   - 415: a body that is not JSON.
   - 503: the database is unavailable.
   - 500: anything unexpected, without internal details.
4. **Nullable is explicit:** every response field is always present (`required`). Fields
   that may have no value use `type: [X, "null"]`, so "unknown" is never confused with
   "missing".
5. **The contract is enforced, not trusted:**
   - `npx @redocly/cli lint openapi.yaml` (rules: `recommended`, in `redocly.yaml`).
   - **Schemathesis** reads the yaml file and sends generated requests to the app. Every
     response must match a documented status code, content type and schema.
   - A **route parity test**: the (method, path) pairs of the app equal those of the spec.
   - The UI's TypeScript types are **generated** from the spec (`openapi-typescript`). CI
     fails if they are out of date, and `tsc` fails if the UI uses something the contract
     doesn't define.
6. **The UI is built from the contract only.** If it needs data the contract lacks, the
   contract changes first, with an ADR, then the server, then the UI.

## Consequences

- The contract can be reviewed, linted and shared before any code exists, and consumers
  can generate clients from it.
- Writing the schema by hand duplicates information that is also in the Pydantic models.
  The contract tests are what keep the two from drifting apart.
- New dev dependency: `schemathesis`. Redocly runs through `npx` (Node.js), so it adds no
  Python dependency.
- Breaking changes to the contract would need a `/v2`. Additive changes (new optional
  fields, new endpoints) stay in `/v1`.
