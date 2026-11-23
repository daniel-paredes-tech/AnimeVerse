"""Serving the built web UI (web/dist) next to the API, from the same local server.

The UI is a single-page app: React Router decides what /anime/42 shows, in the
browser. So:
- a request for a file that exists in web/dist (a script, a stylesheet, a font)
  gets that file;
- any other path that isn't the API gets index.html, and the app routes it;
- /v1/... never falls back to index.html: an unknown API path stays a 404 problem.

Files are only ever read from inside web/dist: a path that resolves outside it
("/../../.env") gets index.html like any unknown path, never the file.

Vite names built assets by content hash (assets/index-3f9a1c.js), so they can
be cached for a year; index.html is never cached, so a new build shows at once.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

API_PREFIX = "v1"
NO_CACHE = {"Cache-Control": "no-cache"}
LONG_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}


def mount_web_ui(app: FastAPI, dist: Path) -> None:
    """Serve the built UI in `dist` for every GET that the API doesn't answer."""
    root = dist.resolve()
    index = root / "index.html"

    # Registered after the API router, so every /v1 route is matched first.
    @app.get("/{path:path}", include_in_schema=False)
    def web_ui(path: str, request: Request) -> FileResponse:
        if path == API_PREFIX or path.startswith(f"{API_PREFIX}/"):
            raise StarletteHTTPException(404)  # answered as the API's 404 problem
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            hashed = candidate.parent == root / "assets"
            return FileResponse(candidate, headers=LONG_CACHE if hashed else NO_CACHE)
        return FileResponse(index, headers=NO_CACHE)
