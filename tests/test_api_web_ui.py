"""Serving the built web UI next to the API (entrypoints/api/web_ui.py), with a fake web/dist."""

import pytest
from fastapi.testclient import TestClient

from animeverse.application.catalog import BrowseCatalog
from animeverse.application.watchlist import ManageWatchlist
from animeverse.entrypoints.api.app import create_app
from animeverse.entrypoints.api.security import API_CSP, UI_CSP
from tests.fakes import InMemoryCatalogStore

INDEX = "<!doctype html><title>AnimeVerse</title>"


@pytest.fixture
def client(tmp_path) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "assets" / "index-abc123.js").write_text("console.log('app')")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.env").write_text("POSTGRES_PASSWORD=x")  # outside dist: must never be served

    store = InMemoryCatalogStore()
    app = create_app(BrowseCatalog(store), ManageWatchlist(store, store), b"openapi: 3.1.0\n", web_dist=dist)
    return TestClient(app, base_url="http://localhost")


def test_the_root_serves_the_app(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"


def test_app_routes_fall_back_to_index_html(client):
    # React Router decides what /anime/42 shows, so a reload there must load the app.
    for path in ("/anime", "/anime/42", "/some/unknown/page"):
        assert client.get(path).text == INDEX


def test_built_files_are_served_and_hashed_assets_cached_long(client):
    asset = client.get("/assets/index-abc123.js")
    favicon = client.get("/favicon.svg")

    assert asset.text == "console.log('app')"
    assert "immutable" in asset.headers["cache-control"]
    assert favicon.text == "<svg/>"
    assert favicon.headers["cache-control"] == "no-cache"


def test_files_outside_dist_are_never_served(client):
    for path in ("/../secret.env", "/%2e%2e/secret.env", "/assets/../../secret.env"):
        assert "POSTGRES_PASSWORD" not in client.get(path).text


def test_the_api_still_answers_and_unknown_api_paths_stay_404_problems(client):
    assert client.get("/v1/franchises").status_code == 200

    response = client.get("/v1/nothing-here")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_the_ui_and_the_api_get_different_content_security_policies(client):
    assert client.get("/").headers["content-security-policy"] == UI_CSP
    assert client.get("/v1/franchises").headers["content-security-policy"] == API_CSP


def test_the_ui_policy_allows_only_the_app_itself_and_anilist_images():
    assert "img-src 'self' https://s4.anilist.co" in UI_CSP
    assert "script-src 'self'" in UI_CSP
    assert "frame-ancestors 'none'" in UI_CSP
    assert "unsafe" not in UI_CSP
