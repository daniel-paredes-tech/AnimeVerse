"""Keeping the API local-only (ADR 0009).

1. The server binds to 127.0.0.1 (server.py), so other devices can't connect.
2. This middleware refuses requests whose Host header is not this computer.
   That blocks "DNS rebinding": a malicious website pointing its own domain at
   127.0.0.1 so the browser lets it read (and write) a local API.
3. Every response carries security headers: no sniffing of content types, no
   referrer, and no embedding in other sites.
"""

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from animeverse.entrypoints.api.problems import field_error, problem

LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # JSON needs nothing from a page: no scripts, no styles, never framed.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def is_local_host(host_header: str | None, allowed: frozenset[str] = LOCAL_HOSTNAMES) -> bool:
    """True if a Host header names an allowed host: 'localhost:8000', '127.0.0.1', '[::1]:8000'."""
    if not host_header:
        return False
    try:
        hostname = urlsplit(f"//{host_header}").hostname  # strips the port and IPv6 brackets
    except ValueError:  # malformed, e.g. an unclosed "[" bracket
        return False
    return hostname in allowed


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Callable[..., Awaitable[None]], allowed_hosts: frozenset[str] = LOCAL_HOSTNAMES) -> None:
        super().__init__(app)
        self._allowed = allowed_hosts

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not is_local_host(request.headers.get("host"), self._allowed):
            response: Response = problem(
                request,
                400,
                "invalid-request",
                "This API only answers requests for localhost.",
                [field_error("header", "Host", "not_allowed", "Must be localhost or 127.0.0.1.")],
            )
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
