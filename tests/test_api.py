"""Behaviour of the REST API, with the in-memory store: no database, no network.

tests/test_api_contract.py proves every response matches openapi.yaml; these
tests prove the answers are the right ones (links, status codes, error fields).

All anime below are made-up test data.
"""

import socket
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from animeverse.application.catalog import BrowseCatalog
from animeverse.application.watchlist import ManageWatchlist
from animeverse.domain.models import Anime, Franchise
from animeverse.entrypoints.api import server
from animeverse.entrypoints.api.app import create_app
from tests.fakes import InMemoryCatalogStore

CONTRACT = b"openapi: 3.1.0\n"
ENTRY = {"status": "watching", "episodes_watched": 12, "rating": 8, "notes": "Good so far."}


@pytest.fixture
def store() -> InMemoryCatalogStore:
    store = InMemoryCatalogStore()
    with store.session() as session:
        naruto = session.save_franchise(Franchise("Naruto", "Naruto"))
        session.save_member(
            naruto,
            Anime(
                anilist_id=900001,
                title="Test Anime",
                type="TV",
                status="FINISHED",
                episodes=24,
                score=Decimal("8.20"),
                popularity=300,
            ),
        )
        session.save_member(naruto, Anime(anilist_id=900002, title="Second", popularity=200))
        session.save_member(naruto, Anime(anilist_id=900003, title="Third", popularity=100))
    return store


@pytest.fixture
def client(store) -> TestClient:
    app = create_app(BrowseCatalog(store), ManageWatchlist(store, store), CONTRACT)
    return TestClient(app, base_url="http://localhost")


def errors(response) -> list[tuple[str, str, str]]:
    return [(e["location"], e["field"], e["code"]) for e in response.json()["errors"]]


# --- The list ---------------------------------------------------------------------------------


def test_list_returns_data_meta_and_links(client):
    response = client.get("/v1/anime", params={"page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert [a["title"] for a in body["data"]] == ["Test Anime", "Second"]
    assert body["meta"] == {"page": 1, "page_size": 2, "total_items": 3, "total_pages": 2}
    assert body["links"] == {
        "self": "/v1/anime?sort=-popularity&page=1&page_size=2",
        "next": "/v1/anime?sort=-popularity&page=2&page_size=2",
        "prev": None,
    }


def test_links_keep_the_filters(client):
    body = client.get("/v1/anime", params={"franchise": 1, "on_watchlist": "false", "page": 2, "page_size": 1}).json()

    assert body["links"]["prev"] == "/v1/anime?franchise=1&on_watchlist=false&sort=-popularity&page=1&page_size=1"
    assert body["links"]["next"] == "/v1/anime?franchise=1&on_watchlist=false&sort=-popularity&page=3&page_size=1"


def test_a_list_item_uses_the_contract_names_and_leaves_out_the_synopsis(client):
    item = client.get("/v1/anime").json()["data"][0]

    assert item["format"] == "TV"  # stored as anime.type
    assert item["score"] == 8.2  # a JSON number, from Decimal("8.20")
    assert item["watchlist_entry"] is None
    assert item["franchises"] == [{"id": 1, "name": "Naruto"}]
    assert "synopsis" not in item


def test_a_page_past_the_end_is_empty_not_an_error(client):
    response = client.get("/v1/anime", params={"page": 99})

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["total_items"] == 3


def test_filters_and_sort_reach_the_query(client):
    body = client.get("/v1/anime", params={"q": "SEC", "sort": "title"}).json()

    assert [a["title"] for a in body["data"]] == ["Second"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"page_size": 101}, ("query", "page_size", "too_large")),
        ({"page": 0}, ("query", "page", "too_small")),
        ({"status": "AIRING"}, ("query", "status", "not_allowed")),
        ({"sort": "random"}, ("query", "sort", "not_allowed")),
        ({"franchise": "naruto"}, ("query", "franchise", "invalid_type")),
        ({"q": ""}, ("query", "q", "too_small")),
        ({"q": "a\x00b"}, ("query", "q", "invalid_characters")),
        ({"fransise": 1}, ("query", "fransise", "not_allowed")),  # unknown parameter: a typo
        ({"year_from": 2010, "year_to": 2000}, ("query", "year_to", "too_small")),  # the use case's rule
    ],
)
def test_invalid_list_parameters_are_a_400_problem(client, params, expected):
    response = client.get("/v1/anime", params=params)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "urn:animeverse:problem:invalid-request"
    assert errors(response) == [expected]


# --- One anime --------------------------------------------------------------------------------


def test_get_one_anime_has_every_field(client, store):
    body = client.get(f"/v1/anime/{store.anime_id_of(900001)}").json()

    assert body["title"] == "Test Anime"
    for nullable in ("mal_id", "synopsis", "aired_from", "aired_to", "anilist_url"):
        assert body[nullable] is None  # present, and null when unknown
    assert body["updated_at"]


def test_an_unknown_anime_is_a_404_problem(client):
    response = client.get("/v1/anime/9999")

    assert response.status_code == 404
    assert response.json() == {
        "type": "urn:animeverse:problem:not-found",
        "title": "Resource not found",
        "status": 404,
        "detail": "There is no anime with id 9999.",
        "instance": "/v1/anime/9999",
    }


@pytest.mark.parametrize(("anime_id", "code"), [("0", "too_small"), ("abc", "invalid_type")])
def test_an_invalid_id_is_a_400_problem(client, anime_id, code):
    response = client.get(f"/v1/anime/{anime_id}")

    assert response.status_code == 400
    assert errors(response) == [("path", "anime_id", code)]


# --- The watchlist ----------------------------------------------------------------------------


def test_put_creates_then_replaces(client, store):
    url = f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry"

    created = client.put(url, json=ENTRY)
    replaced = client.put(url, json={**ENTRY, "status": "completed", "episodes_watched": 24})

    assert created.status_code == 201
    assert created.headers["location"] == url
    assert created.json()["status"] == "watching"
    assert replaced.status_code == 200
    assert replaced.json()["status"] == "completed"
    assert replaced.json()["created_at"] == created.json()["created_at"]


def test_the_entry_appears_on_the_anime(client, store):
    anime_id = store.anime_id_of(900001)
    client.put(f"/v1/anime/{anime_id}/watchlist-entry", json=ENTRY)

    entry = client.get(f"/v1/anime/{anime_id}").json()["watchlist_entry"]

    assert (entry["status"], entry["episodes_watched"], entry["rating"]) == ("watching", 12, 8)
    assert client.get("/v1/anime", params={"on_watchlist": "true"}).json()["meta"]["total_items"] == 1


def test_blank_notes_are_stored_as_null(client, store):
    response = client.put(f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry", json={**ENTRY, "notes": "  "})

    assert response.json()["notes"] is None


def test_breaking_a_rule_is_a_422_with_the_rule_code(client, store):
    response = client.put(
        f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry", json={**ENTRY, "episodes_watched": 25}
    )

    assert response.status_code == 422
    assert response.json()["type"] == "urn:animeverse:problem:validation-error"
    assert response.json()["detail"] == "The watchlist entry breaks 1 rule."
    assert errors(response) == [("body", "episodes_watched", "exceeds_episodes")]
    assert response.json()["errors"][0]["message"] == "Can't be more than the anime's 24 episodes."


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({**ENTRY, "rating": 11}, [("body", "rating", "too_large")]),
        ({**ENTRY, "status": "finished"}, [("body", "status", "not_allowed")]),
        ({**ENTRY, "episodes_watched": "12"}, [("body", "episodes_watched", "invalid_type")]),  # strict: no "12"
        ({**ENTRY, "episodes_watched": True}, [("body", "episodes_watched", "invalid_type")]),
        ({**ENTRY, "favourite": True}, [("body", "favourite", "not_allowed")]),
        ({**ENTRY, "notes": "x" * 1001}, [("body", "notes", "too_long")]),
        ({**ENTRY, "notes": "a\x00b"}, [("body", "notes", "invalid_characters")]),
        (
            {"status": "watching"},
            [("body", "episodes_watched", "required"), ("body", "rating", "required"), ("body", "notes", "required")],
        ),
    ],
)
def test_a_body_that_breaks_the_schema_is_a_422_listing_every_field(client, store, body, expected):
    response = client.put(f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry", json=body)

    assert response.status_code == 422
    assert errors(response) == expected


@pytest.mark.parametrize("content", [b"{not json", b"", b'{"episodes_watched": NaN}'])
def test_broken_json_is_a_400(client, store, content):
    response = client.put(
        f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry",
        content=content,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert errors(response) == [("body", "", "invalid_json")]


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/x-www-form-urlencoded"])
def test_a_body_that_is_not_json_is_a_415(client, store, content_type):
    headers = {"content-type": content_type} if content_type else {}

    response = client.put(f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry", content=b"x", headers=headers)

    assert response.status_code == 415
    assert response.json()["type"] == "urn:animeverse:problem:unsupported-media-type"


def test_putting_for_an_unknown_anime_is_a_404(client):
    assert client.put("/v1/anime/9999/watchlist-entry", json=ENTRY).status_code == 404


def test_delete_removes_the_entry_then_404s(client, store):
    url = f"/v1/anime/{store.anime_id_of(900001)}/watchlist-entry"
    client.put(url, json=ENTRY)

    first = client.delete(url)
    second = client.delete(url)

    assert first.status_code == 204
    assert first.content == b""
    assert second.status_code == 404
    assert "is not on your watchlist" in second.json()["detail"]


# --- Franchises, the contract, errors -----------------------------------------------------------


def test_franchises(client):
    assert client.get("/v1/franchises").json() == {"data": [{"id": 1, "name": "Naruto", "anime_count": 3}]}


def test_the_contract_is_served_as_is(client):
    response = client.get("/v1/openapi.yaml")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/yaml"
    assert response.content == CONTRACT


def test_a_database_outage_is_a_503_problem(client, store):
    store.unavailable = True

    response = client.get("/v1/anime")

    assert response.status_code == 503
    assert response.json()["type"] == "urn:animeverse:problem:service-unavailable"
    assert response.json()["detail"] == "The database is unavailable. Try again later."


def test_a_bug_is_a_500_without_internal_details(store):
    class Broken(BrowseCatalog):
        def list_franchises(self):
            raise RuntimeError("secret internal detail")

    app = create_app(Broken(store), ManageWatchlist(store, store), CONTRACT)
    response = TestClient(app, base_url="http://localhost", raise_server_exceptions=False).get("/v1/franchises")

    assert response.status_code == 500
    assert response.json()["type"] == "urn:animeverse:problem:internal-error"
    assert "secret" not in response.text


def test_an_unknown_path_is_a_404_problem(client):
    response = client.get("/v2/anime")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_a_wrong_method_is_a_405_listing_every_allowed_method(client):
    response = client.post("/v1/anime/1/watchlist-entry", json=ENTRY)

    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, PUT"


# --- Local only ---------------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example", "localhost.evil.example", "192.168.1.10:8000"])
def test_requests_for_other_hosts_are_refused(client, host):
    response = client.get("/v1/anime", headers={"host": host})

    assert response.status_code == 400
    assert errors(response) == [("header", "Host", "not_allowed")]


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000"])
def test_local_hosts_are_accepted(client, host):
    assert client.get("/v1/franchises", headers={"host": host}).status_code == 200


def test_security_headers_are_always_sent(client):
    for response in (client.get("/v1/anime"), client.get("/v1/anime/9999")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_serve_reports_a_busy_port(client, caplog):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]

        assert server.serve(client.app, port=port) == 2

    assert "already in use" in caplog.text
