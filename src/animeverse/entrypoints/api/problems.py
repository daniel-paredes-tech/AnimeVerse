"""Every error answered as RFC 9457 Problem Details (application/problem+json), as openapi.yaml says.

One shape for every error: type, title, status, detail, instance, plus
`errors` (one item per invalid field) for 400 and 422.

    What went wrong                                   Status  type (urn:animeverse:problem:...)
    bad query/path parameter, broken JSON, bad Host   400     invalid-request
    unknown anime or watchlist entry, unknown route   404     not-found
    a method the path doesn't support                 405     method-not-allowed
    a body that isn't application/json                415     unsupported-media-type
    a JSON body that breaks the schema or a rule      422     validation-error
    the database is unavailable                       503     service-unavailable
    anything unexpected (a bug)                       500     internal-error

A 500 never shows internal details: the traceback goes to the log only.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from animeverse.application.errors import InvalidQuery, InvalidWatchlistEntry, NotFound
from animeverse.application.ports import StoreUnavailable
from animeverse.domain.watchlist import RuleViolation

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"
Location = Literal["body", "query", "path", "header"]

# type slug -> title. A title is the same for every occurrence of its type.
TITLES = {
    "invalid-request": "Invalid request",
    "validation-error": "Validation failed",
    "not-found": "Resource not found",
    "method-not-allowed": "Method not allowed",
    "unsupported-media-type": "Unsupported media type",
    "service-unavailable": "Service unavailable",
    "internal-error": "Internal error",
}


class FieldProblem(Exception):
    """Raised by the routes for a 400 or 422 with field errors (e.g. unknown query parameters)."""

    def __init__(self, status: int, detail: str, errors: list[dict[str, str]]) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.errors = errors


class UnsupportedMediaType(Exception):
    """The request body is not application/json."""


def problem(
    request: Request,
    status: int,
    slug: str,
    detail: str,
    errors: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:animeverse:problem:{slug}",
        "title": TITLES[slug],
        "status": status,
        "detail": detail,
        "instance": request_path(request),
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def request_path(request: Request) -> str:
    """The path exactly as the client sent it, still percent-encoded ("/v1/anime/%20").

    request.url.path is decoded ("/v1/anime/ "), and a raw space is not a valid
    URI reference, which the contract requires for `instance` and `Location`.
    """
    raw = request.scope.get("raw_path")
    return raw.decode("latin-1") if raw else request.url.path


def field_error(location: Location, field: str, code: str, message: str) -> dict[str, str]:
    return {"location": location, "field": field, "code": code, "message": message}


def from_violations(location: Location, violations: Sequence[RuleViolation]) -> list[dict[str, str]]:
    return [field_error(location, v.field, v.code, v.message) for v in violations]


# --- Pydantic's errors in the contract's vocabulary ---------------------------------------

# Pydantic error type -> the contract's FieldError.code (openapi.yaml lists them).
_CODES = {
    "missing": "required",
    "extra_forbidden": "not_allowed",
    "literal_error": "not_allowed",
    "enum": "not_allowed",
    "greater_than_equal": "too_small",
    "greater_than": "too_small",
    "less_than_equal": "too_large",
    "less_than": "too_large",
    "string_too_short": "too_small",
    "string_too_long": "too_long",
    "string_pattern_mismatch": "invalid_characters",
    "json_invalid": "invalid_json",
}


def _message(error: Any) -> str:
    ctx = error.get("ctx") or {}
    match error["type"]:
        case "missing":
            return "This field is required."
        case "extra_forbidden":
            return "This field is not allowed."
        case "literal_error" | "enum":
            return f"Must be one of {ctx.get('expected', 'the allowed values')}."
        case "greater_than_equal":
            return f"Must be at least {ctx['ge']}."
        case "less_than_equal":
            return f"Must be at most {ctx['le']}."
        case "string_too_short":
            return f"Must be at least {ctx['min_length']} character(s)."
        case "string_too_long":
            return f"Must be at most {ctx['max_length']} characters."
        case "string_pattern_mismatch":
            return "Must not contain NUL characters."
        case "json_invalid":
            return "The body is not valid JSON."
    return str(error["msg"])  # Pydantic's own message, e.g. "Input should be a valid integer"


def from_pydantic(location: Location, errors: Sequence[Any], skip: int = 0) -> list[dict[str, str]]:
    """Field errors from Pydantic errors. `skip` drops leading loc parts (e.g. "query")."""
    result = []
    for error in errors:
        field = ".".join(str(part) for part in error["loc"][skip:])
        code = _CODES.get(error["type"], "invalid_type" if error["type"].endswith(("_type", "_parsing")) else "invalid")
        result.append(field_error(location, field, code, _message(error)))
    return result


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --- Handlers -----------------------------------------------------------------------------


def install(app: FastAPI, allowed_methods: Callable[[str], list[str]]) -> None:
    """Register a handler for every error the API can meet.

    allowed_methods(path) lists every method the API supports for a path, for the
    Allow header of a 405 (HTTP requires all of them, not only the first route's).
    """

    @app.exception_handler(RequestValidationError)
    async def invalid_parameters(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Only query and path parameters reach here: the PUT body is validated by the route.
        errors = [
            field_error(e["loc"][0], ".".join(str(p) for p in e["loc"][1:]), *_code_and_message(e))
            for e in exc.errors()
        ]
        return problem(
            request, 400, "invalid-request", f"The request has {_count(len(errors), 'invalid parameter')}.", errors
        )

    @app.exception_handler(FieldProblem)
    async def field_problem(request: Request, exc: FieldProblem) -> JSONResponse:
        slug = "validation-error" if exc.status == 422 else "invalid-request"
        return problem(request, exc.status, slug, exc.detail, exc.errors)

    @app.exception_handler(ValidationError)
    async def invalid_body(request: Request, exc: ValidationError) -> JSONResponse:
        errors = from_pydantic("body", exc.errors())
        detail = f"The request body has {_count(len(errors), 'invalid field')}."
        return problem(request, 422, "validation-error", detail, errors)

    @app.exception_handler(InvalidQuery)
    async def invalid_query(request: Request, exc: InvalidQuery) -> JSONResponse:
        errors = from_violations("query", exc.violations)
        return problem(
            request, 400, "invalid-request", f"The request has {_count(len(errors), 'invalid parameter')}.", errors
        )

    @app.exception_handler(InvalidWatchlistEntry)
    async def invalid_entry(request: Request, exc: InvalidWatchlistEntry) -> JSONResponse:
        errors = from_violations("body", exc.violations)
        return problem(
            request, 422, "validation-error", f"The watchlist entry breaks {_count(len(errors), 'rule')}.", errors
        )

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound) -> JSONResponse:
        return problem(request, 404, "not-found", str(exc))

    @app.exception_handler(UnsupportedMediaType)
    async def unsupported_media_type(request: Request, exc: UnsupportedMediaType) -> JSONResponse:
        return problem(
            request, 415, "unsupported-media-type", "The request body must be JSON (Content-Type: application/json)."
        )

    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(request: Request, exc: StoreUnavailable) -> JSONResponse:
        logger.error("Database unavailable during %s %s: %s", request.method, request.url.path, exc)
        return problem(request, 503, "service-unavailable", "The database is unavailable. Try again later.")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Raised by the router itself: unknown path (404), unsupported method (405).
        if exc.status_code == 405:
            allowed = ", ".join(allowed_methods(request.url.path))
            return problem(
                request, 405, "method-not-allowed", f"{request.method} is not allowed here.", headers={"Allow": allowed}
            )
        if exc.status_code == 404:
            return problem(request, 404, "not-found", f"There is nothing at {request.url.path}.")
        logger.error("Unexpected HTTP error %s on %s %s", exc.status_code, request.method, request.url.path)
        return problem(request, 500, "internal-error", "Something went wrong on our side.")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected error during %s %s", request.method, request.url.path)
        return problem(request, 500, "internal-error", "Something went wrong on our side.")


def _code_and_message(error: Any) -> tuple[str, str]:
    item = from_pydantic("query", [error])[0]
    return item["code"], item["message"]
