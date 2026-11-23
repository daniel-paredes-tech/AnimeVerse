"""The API matches openapi.yaml, the contract (ADR 0010).

1. Route parity: the API has exactly the operations the contract declares,
   no more and no fewer.
2. Schemathesis reads openapi.yaml (the file, not anything generated from the
   code) and sends many generated requests, valid and invalid, to the API.
   Every response must use a documented status code, content type and headers,
   and its body must match the documented schema.

The API under test runs on the PostgreSQL test database with a few made-up
anime, so the real SQL, decimals and timestamps are what gets checked.
"""

from pathlib import Path

import pytest
import schemathesis
import yaml
from fastapi.routing import APIRoute

from animeverse.application.catalog import BrowseCatalog
from animeverse.application.watchlist import ManageWatchlist
from animeverse.domain.models import Anime, Franchise
from animeverse.domain.watchlist import WatchlistEntry, WatchStatus
from animeverse.entrypoints.api.app import create_app
from animeverse.entrypoints.api.routes import router
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import (
    PostgresCatalogQuery,
    PostgresCatalogStore,
    PostgresWatchlistStore,
)

SPEC = Path(__file__).resolve().parent.parent / "openapi.yaml"
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}


def test_the_api_has_exactly_the_operations_of_the_contract():
    spec = yaml.safe_load(SPEC.read_text())
    declared = {
        (method.upper(), path) for path, item in spec["paths"].items() for method in item if method in HTTP_METHODS
    }

    # The router declares the full /v1 paths; create_app includes it without a prefix.
    # (If it weren't included, every Schemathesis case below would get a 404 and fail.)
    implemented = {
        (method, route.path) for route in router.routes if isinstance(route, APIRoute) for method in route.methods
    }

    assert implemented == declared


@pytest.fixture
def api_schema(committing_conn, test_db_settings):
    """openapi.yaml, pointed at the API running on the test database."""
    with PostgresCatalogStore(committing_conn).session() as session:
        naruto = session.save_franchise(Franchise("Naruto", "Naruto"))
        # id 1 is the example id in the contract, so its examples reach a real anime.
        session.save_member(naruto, Anime(anilist_id=900001, title="Test Anime", episodes=220, score=None))
        session.save_member(naruto, Anime(anilist_id=900002, title="Still Airing", status="RELEASING"))
    query = PostgresCatalogQuery(lambda: connect(test_db_settings))
    watchlist = PostgresWatchlistStore(lambda: connect(test_db_settings))
    watchlist.save(2, WatchlistEntry(WatchStatus.WATCHING, 3, rating=7, notes=None))

    app = create_app(BrowseCatalog(query), ManageWatchlist(query, watchlist), SPEC.read_bytes())
    schema = schemathesis.openapi.from_path(SPEC)
    schema.app = app
    return schema


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
def test_the_api_follows_the_contract(case):
    case.call_and_validate()
