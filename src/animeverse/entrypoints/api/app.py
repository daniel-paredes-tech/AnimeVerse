"""The API application factory.

create_app() receives everything it needs (the use cases, the contract
document), so tests build it with in-memory fakes and the CLI (the
composition root) builds it with PostgreSQL. The API never picks an
implementation itself.

FastAPI's own generated OpenAPI document and docs pages are turned off:
openapi.yaml, written by hand, is the only contract (ADR 0010). The API
serves that file at /v1/openapi.yaml.

When a built web UI is given (web/dist), the same server serves it at /.
"""

from pathlib import Path

from fastapi import FastAPI

from animeverse.application.catalog import BrowseCatalog
from animeverse.application.watchlist import ManageWatchlist
from animeverse.entrypoints.api import problems
from animeverse.entrypoints.api.routes import allowed_methods, router
from animeverse.entrypoints.api.security import LOCAL_HOSTNAMES, LocalOnlyMiddleware
from animeverse.entrypoints.api.web_ui import mount_web_ui


def create_app(
    browse: BrowseCatalog,
    watchlist: ManageWatchlist,
    openapi_document: bytes,
    allowed_hosts: frozenset[str] = LOCAL_HOSTNAMES,
    web_dist: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="AnimeVerse API", openapi_url=None, docs_url=None, redoc_url=None)
    app.state.browse = browse
    app.state.watchlist = watchlist
    app.state.openapi_document = openapi_document
    app.add_middleware(LocalOnlyMiddleware, allowed_hosts=allowed_hosts)
    problems.install(app, allowed_methods)
    app.include_router(router)
    if web_dist is not None:
        mount_web_ui(app, web_dist)  # after the API, so /v1 routes always win
    return app
