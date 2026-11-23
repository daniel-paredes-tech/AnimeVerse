"""The API's endpoints, exactly the paths and parameters declared in openapi.yaml.

Each route only translates: HTTP in -> a use case call -> HTTP out. The rules
live in the use cases and the domain; the errors they raise become Problem
Details in problems.py.

    GET    /v1/anime                          list with filters, sort and pages
    GET    /v1/anime/{anime_id}               one anime
    PUT    /v1/anime/{anime_id}/watchlist-entry  create or replace your entry
    DELETE /v1/anime/{anime_id}/watchlist-entry  remove it
    GET    /v1/franchises                     every franchise with its anime count
    GET    /v1/openapi.yaml                   the contract itself

tests/test_api_contract.py checks that these are exactly the contract's
operations (route parity) and runs Schemathesis against openapi.yaml.
"""

import json
from decimal import Decimal
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from animeverse.application.catalog import MAX_PAGE_SIZE, BrowseCatalog
from animeverse.application.ports import AnimeFilters, PageRequest, Sort, SortField
from animeverse.application.watchlist import ManageWatchlist
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from animeverse.entrypoints.api import schemas
from animeverse.entrypoints.api.problems import FieldProblem, UnsupportedMediaType, field_error, request_path

router = APIRouter(prefix="/v1")

MAX_ID = 2_147_483_647  # PostgreSQL INTEGER

ReleaseStatus = Literal["FINISHED", "RELEASING", "NOT_YET_RELEASED", "CANCELLED", "HIATUS"]
AnimeFormat = Literal["TV", "TV_SHORT", "MOVIE", "SPECIAL", "OVA", "ONA", "MUSIC"]
WatchStatusValue = Literal["planning", "watching", "completed", "paused", "dropped"]
SortValue = Literal["popularity", "-popularity", "score", "-score", "start_year", "-start_year", "title", "-title"]

AnimeId = Annotated[int, Path(ge=1, le=MAX_ID)]


# --- Dependencies ---------------------------------------------------------------------------


def get_browse(request: Request) -> BrowseCatalog:
    browse: BrowseCatalog = request.app.state.browse
    return browse


def get_watchlist(request: Request) -> ManageWatchlist:
    watchlist: ManageWatchlist = request.app.state.watchlist
    return watchlist


def only_query_parameters(*allowed: str) -> Any:  # Any: what FastAPI's Depends() returns
    """Refuse unknown query parameters with 400, so `?fransise=1` is reported instead of ignored."""
    allowed_names = frozenset(allowed)

    def check(request: Request) -> None:
        unknown = sorted(set(request.query_params.keys()) - allowed_names)
        if unknown:
            errors = [field_error("query", n, "not_allowed", "Unknown query parameter.") for n in unknown]
            raise FieldProblem(400, f"The request has {len(errors)} unknown query parameter(s).", errors)

    return Depends(check)


def _json(model: BaseModel, status: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(model.model_dump(mode="json"), status_code=status, headers=headers)


# --- Anime ------------------------------------------------------------------------------------

LIST_PARAMETERS = (
    "q",
    "franchise",
    "status",
    "format",
    "year_from",
    "year_to",
    "min_score",
    "on_watchlist",
    "watchlist_status",
    "sort",
    "page",
    "page_size",
)


@router.get("/anime", dependencies=[only_query_parameters(*LIST_PARAMETERS)])
def list_anime(
    request: Request,
    browse: Annotated[BrowseCatalog, Depends(get_browse)],
    q: Annotated[str | None, Query(min_length=1, max_length=100, pattern=schemas.NO_NUL)] = None,
    franchise: Annotated[int | None, Query(ge=1, le=MAX_ID)] = None,
    status: ReleaseStatus | None = None,
    format: AnimeFormat | None = None,
    year_from: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    min_score: Annotated[float | None, Query(ge=0, le=10)] = None,
    on_watchlist: bool | None = None,
    watchlist_status: WatchStatusValue | None = None,
    sort: SortValue = "-popularity",
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 24,
) -> JSONResponse:
    filters = AnimeFilters(
        text=q,
        franchise_id=franchise,
        status=status,
        format=format,
        year_from=year_from,
        year_to=year_to,
        min_score=Decimal(str(min_score)) if min_score is not None else None,  # 7.5 -> Decimal("7.5"), exact
        on_watchlist=on_watchlist,
        watchlist_status=WatchStatus(watchlist_status) if watchlist_status else None,
    )
    order = Sort(SortField(sort.removeprefix("-")), descending=sort.startswith("-"))
    result = browse.list_anime(filters, order, PageRequest(page, page_size))

    # The links repeat the filters that were given, so a client can follow them as they are.
    given = {
        "q": q,
        "franchise": franchise,
        "status": status,
        "format": format,
        "year_from": year_from,
        "year_to": year_to,
        "min_score": min_score,
        "on_watchlist": None if on_watchlist is None else str(on_watchlist).lower(),
        "watchlist_status": watchlist_status,
        "sort": sort,
    }
    kept = {name: value for name, value in given.items() if value is not None}

    def link(number: int) -> str:
        return f"{request.url.path}?{urlencode({**kept, 'page': number, 'page_size': page_size})}"

    links = schemas.PageLinksOut(
        self=link(page),
        next=link(page + 1) if page < result.total_pages else None,
        prev=link(page - 1) if page > 1 else None,
    )
    return _json(schemas.from_page(result, links))


@router.get("/anime/{anime_id}", dependencies=[only_query_parameters()])
def get_anime(anime_id: AnimeId, browse: Annotated[BrowseCatalog, Depends(get_browse)]) -> JSONResponse:
    return _json(schemas.from_detail(browse.get_anime(anime_id)))


# --- Watchlist --------------------------------------------------------------------------------


@router.put("/anime/{anime_id}/watchlist-entry", dependencies=[only_query_parameters()])
async def put_watchlist_entry(
    request: Request, anime_id: AnimeId, watchlist: Annotated[ManageWatchlist, Depends(get_watchlist)]
) -> JSONResponse:
    # The body is read here, not by FastAPI, so the checks run in a clear order:
    # 415 not JSON -> 400 broken JSON -> 422 breaks the schema -> 404 / 422 from the use case.
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise UnsupportedMediaType()
    data = _parse_json(await request.body())
    body = schemas.WatchlistEntryInput.model_validate(data)  # ValidationError -> 422

    entry = WatchlistEntry(WatchStatus(body.status), body.episodes_watched, body.rating, body.notes)
    # The use case is blocking (it waits on the database): run it off the event loop.
    saved = await run_in_threadpool(watchlist.save, anime_id, entry)

    out = schemas.from_watchlist_entry(saved.stored)
    assert out is not None  # a saved entry always exists
    if saved.created:
        return _json(out, status=201, headers={"Location": request_path(request)})
    return _json(out)


@router.delete("/anime/{anime_id}/watchlist-entry", dependencies=[only_query_parameters()])
def delete_watchlist_entry(
    anime_id: AnimeId, watchlist: Annotated[ManageWatchlist, Depends(get_watchlist)]
) -> Response:
    watchlist.remove(anime_id)
    return Response(status_code=204)


def _parse_json(raw: bytes) -> object:
    def refuse(constant: str) -> object:
        raise ValueError(f"{constant} is not valid JSON")  # Python accepts NaN/Infinity; JSON doesn't

    try:
        return json.loads(raw, parse_constant=refuse)
    except (ValueError, UnicodeDecodeError):
        error = field_error("body", "", "invalid_json", "The body is not valid JSON.")
        raise FieldProblem(400, "The request body is not valid JSON.", [error]) from None


def allowed_methods(path: str) -> list[str]:
    """Every method the API supports for this path (for the Allow header of a 405)."""
    methods = {
        method
        for route in router.routes
        if isinstance(route, APIRoute) and route.path_regex.match(path)
        for method in route.methods or ()
    }
    return sorted(methods)


# --- Franchises and the contract --------------------------------------------------------------


@router.get("/franchises", dependencies=[only_query_parameters()])
def list_franchises(browse: Annotated[BrowseCatalog, Depends(get_browse)]) -> JSONResponse:
    return _json(schemas.from_franchises(browse.list_franchises()))


@router.get("/openapi.yaml", dependencies=[only_query_parameters()])
def get_openapi_document(request: Request) -> Response:
    document: bytes = request.app.state.openapi_document
    return Response(document, media_type="application/yaml")
