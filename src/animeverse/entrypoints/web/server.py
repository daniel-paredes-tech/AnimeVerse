"""Private, read-only local page with the stored anime.

    docker compose up -d
    animeverse serve --open      # http://localhost:8000

Read-only: the page reads through the CatalogReader port; it never calls
AniList and never writes. To refresh the data, run `animeverse import`.

Local only:
- The server listens on 127.0.0.1, so other devices on the network can't reach it.
- Requests whose Host header is not localhost are refused. This blocks "DNS
  rebinding", where a malicious website tricks the browser into reading a
  local page.
- The page loads nothing from outside (see page.py), and security headers
  forbid scripts, external resources and embedding in other sites.

Built on Python's standard library (http.server): no web framework needed.
"""

import errno
import logging
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from animeverse.application.ports import CatalogReader, StoreUnavailable
from animeverse.entrypoints.web.page import render_page

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
SECURITY_HEADERS = {
    # No scripts, no external resources; inline <style> only; can't be embedded in other sites.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def is_local_host(host_header: str | None) -> bool:
    """True if a Host header names this computer: 'localhost:8000', '127.0.0.1', '[::1]:8000'."""
    if not host_header:
        return False
    try:
        hostname = urlsplit(f"//{host_header}").hostname  # strips the port and IPv6 brackets
    except ValueError:  # malformed, e.g. an unclosed "[" bracket
        return False
    return hostname in LOCAL_HOSTNAMES


def make_handler(reader: CatalogReader) -> type[BaseHTTPRequestHandler]:
    """Build the request handler. The reader is passed in, so tests can use fake data."""

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
                data = reader.anime_by_franchise()
            except StoreUnavailable as exc:
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


def serve(reader: CatalogReader, port: int = DEFAULT_PORT, open_browser: bool = False) -> int:
    """Serve the page until Ctrl+C. Returns an exit code: 0 stopped normally, 2 port busy."""
    try:
        # 127.0.0.1 only: the page is not reachable from other devices on the network.
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(reader))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            logger.error("Port %d is already in use (is another local page running?). Try: --port %d", port, port + 1)
            return 2
        raise

    url = f"http://localhost:{port}/"
    logger.info("Serving %s (press Ctrl+C to stop)", url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")
    finally:
        server.server_close()
    return 0
