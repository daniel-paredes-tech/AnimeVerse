"""Private, read-only local page with the anime stored in PostgreSQL.

    docker compose up -d
    .venv/bin/python -m animeverse.server --open      # http://localhost:8000

Read-only: the page never calls AniList and never writes to the database.
To refresh the data, run the import command (python -m animeverse.import_anime).

Local only:
- The server listens on 127.0.0.1, so other devices on the network can't reach it.
- Requests whose Host header is not localhost are refused. This blocks "DNS
  rebinding", where a malicious website tricks the browser into reading a
  local page.
- The page loads nothing from outside (see page.py), and security headers
  forbid scripts, external resources and embedding in other sites.

Built on Python's standard library (http.server): no web framework needed.
"""

import argparse
import errno
import logging
import sys
import webbrowser
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

import psycopg

from animeverse.config.settings import ConfigError, DatabaseSettings, load_database_settings
from animeverse.domain.models import Anime
from animeverse.page import render_page
from animeverse.repository import connect, list_anime_by_franchise

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
SECURITY_HEADERS = {
    # No scripts, no external resources; inline <style> only; can't be embedded in other sites.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

LoadData = Callable[[], dict[str, list[Anime]]]


def is_local_host(host_header: str | None) -> bool:
    """True if a Host header names this computer: 'localhost:8000', '127.0.0.1', '[::1]:8000'."""
    if not host_header:
        return False
    try:
        hostname = urlsplit(f"//{host_header}").hostname  # strips the port and IPv6 brackets
    except ValueError:  # malformed, e.g. an unclosed "[" bracket
        return False
    return hostname in LOCAL_HOSTNAMES


def load_from_database(settings: DatabaseSettings) -> LoadData:
    """A function that reads the current data, opening a fresh connection each time."""

    def load() -> dict[str, list[Anime]]:
        with connect(settings) as conn:
            return list_anime_by_franchise(conn)

    return load


def make_handler(load_data: LoadData) -> type[BaseHTTPRequestHandler]:
    """Build the request handler. load_data is passed in so tests can use fake data."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "AnimeVerse"
        sys_version = ""  # don't advertise the Python version

        def do_GET(self) -> None:
            if not is_local_host(self.headers.get("Host")):
                self._send(HTTPStatus.BAD_REQUEST, "This page only answers requests for localhost.")
                return
            if urlsplit(self.path).path != "/":
                self._send(HTTPStatus.NOT_FOUND, "Not found. The page is at /.")
                return
            try:
                data = load_data()
            except psycopg.Error as exc:
                logger.error("Could not read the database: %s", exc)
                self._send(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "The database is not reachable. Is it running? Try: docker compose up -d",
                )
                return
            self._send(HTTPStatus.OK, render_page(data), is_html=True)

        def _refuse_method(self) -> None:
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, "Only GET is allowed: this page is read-only.")

        do_POST = do_PUT = do_PATCH = do_DELETE = _refuse_method

        def _send(self, status: HTTPStatus, body: str, is_html: bool = False) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            content_type = "text/html" if is_html else "text/plain"
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            if status == HTTPStatus.METHOD_NOT_ALLOWED:
                self.send_header("Allow", "GET")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            logger.info("%s %s", self.address_string(), format % args)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private, read-only local page with the AnimeVerse data.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to use (default {DEFAULT_PORT})")
    parser.add_argument("--open", action="store_true", help="open the page in your default browser")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    try:
        settings = load_database_settings()
    except ConfigError as exc:
        logger.error("Configuration problem: %s", exc)
        return 2

    try:
        # 127.0.0.1 only: the page is not reachable from other devices on the network.
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(load_from_database(settings)))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.error(
                "Port %d is already in use (is another local page running?). Try: --port %d",
                args.port,
                args.port + 1,
            )
            return 2
        raise

    url = f"http://localhost:{args.port}/"
    logger.info("Serving %s (press Ctrl+C to stop)", url)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
