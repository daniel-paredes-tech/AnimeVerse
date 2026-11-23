"""Keeping the API local-only (ADR 0009).

1. The server binds to 127.0.0.1 (server.py), so other devices can't connect.
2. This middleware refuses requests whose Host header is not this computer.
   That blocks "DNS rebinding": a malicious website pointing its own domain at
   127.0.0.1 so the browser lets it read (and write) a local API.
3. Every response carries security headers: no sniffing of content types, no
   referrer, no embedding in other sites, and a Content-Security-Policy:
   - the API's JSON (/v1/...) needs nothing from a page, so it allows nothing;
   - the web UI may load its own scripts, styles and fonts, call its own API,
     and show cover images from AniList's image server, and nothing else.
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
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"
UI_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; "
    "img-src 'self' https://s4.anilist.co; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


def content_security_policy(path: str) -> str:
    """The API's policy for /v1/..., the web UI's policy for everything else."""
    return API_CSP if path == "/v1" or path.startswith("/v1/") else UI_CSP


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
        response.headers.setdefault("Content-Security-Policy", content_security_policy(request.url.path))
        return response
