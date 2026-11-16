"""Tests for animeverse.server.

The tests start a real server on a free local port (port 0 = let the system
choose) and send real HTTP requests with http.client. No external network.
All anime below are made-up test data.
"""

import http.client
import socket
import threading
from http.server import ThreadingHTTPServer

import psycopg
import pytest

from animeverse import server
from animeverse.models import Anime, Franchise
from animeverse.repository import link_anime_to_franchise, upsert_anime, upsert_franchise

SAMPLE_DATA = {"Test Franchise": [Anime(anilist_id=1, title="Test Anime")]}


@pytest.fixture
def serve():
    """Start a server with the given load_data function; returns its port."""
    running = []

    def _serve(load_data=lambda: SAMPLE_DATA):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(load_data))
        # A short poll interval makes shutdown() fast (the default 0.5 s adds up over many tests).
        threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        running.append(httpd)
        return httpd.server_address[1]

    yield _serve
    for httpd in running:
        httpd.shutdown()
        httpd.server_close()


def request(port, method="GET", path="/", host="localhost"):
    """Send one request with an explicit Host header; returns (response, body)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers={"Host": host})
        response = conn.getresponse()
        return response, response.read().decode("utf-8")
    finally:
        conn.close()


# --- Host check -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("localhost", True),
        ("localhost:8000", True),
        ("LOCALHOST:8000", True),
        ("127.0.0.1:8000", True),
        ("[::1]:8000", True),
        (None, False),
        ("", False),
        ("evil.example", False),
        ("localhost.evil.example", False),
        ("[::1", False),  # malformed
    ],
)
def test_is_local_host(host, expected):
    assert server.is_local_host(host) is expected


# --- Requests ---------------------------------------------------------------------


def test_home_page_shows_the_data(serve):
    response, body = request(serve())

    assert response.status == 200
    assert response.getheader("Content-Type") == "text/html; charset=utf-8"
    assert "Test Franchise" in body and "Test Anime" in body


def test_query_string_is_ignored(serve):
    response, _ = request(serve(), path="/?franchise=x")
    assert response.status == 200


@pytest.mark.parametrize("path", ["/", "/missing"])
def test_security_headers_are_always_sent(serve, path):
    response, _ = request(serve(), path=path)

    assert "default-src 'none'" in response.getheader("Content-Security-Policy")
    assert "frame-ancestors 'none'" in response.getheader("Content-Security-Policy")
    assert response.getheader("X-Content-Type-Options") == "nosniff"
    assert response.getheader("Referrer-Policy") == "no-referrer"


def test_unknown_path_is_not_found(serve):
    response, _ = request(serve(), path="/admin")
    assert response.status == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_only_get_is_allowed(serve, method):
    response, _ = request(serve(), method=method)

    assert response.status == 405
    assert response.getheader("Allow") == "GET"


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "192.168.1.10:8000"])
def test_requests_for_other_hosts_are_refused(serve, host):
    response, body = request(serve(), host=host)

    assert response.status == 400
    assert "Test Anime" not in body


def test_database_failure_gives_a_clear_message(serve):
    def broken():
        raise psycopg.OperationalError("connection refused")

    response, body = request(serve(broken))

    assert response.status == 503
    assert "docker compose up -d" in body


# --- Real database ----------------------------------------------------------------


def test_load_from_database_reads_committed_data(committing_conn, test_db_settings):
    franchise_id = upsert_franchise(committing_conn, Franchise("Test Franchise", "test"))
    anime_id = upsert_anime(committing_conn, Anime(anilist_id=900040, title="Stored Anime")).id
    link_anime_to_franchise(committing_conn, anime_id, franchise_id)
    committing_conn.commit()

    data = server.load_from_database(test_db_settings)()

    assert [a.title for a in data["Test Franchise"]] == ["Stored Anime"]


# --- Command ----------------------------------------------------------------------


def test_main_reports_a_busy_port(monkeypatch, caplog):
    monkeypatch.setattr(server, "load_database_settings", lambda: None)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]

        assert server.main(["--port", str(port)]) == 2

    assert "already in use" in caplog.text
