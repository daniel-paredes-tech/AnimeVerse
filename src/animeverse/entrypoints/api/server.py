"""Running the API with uvicorn, on this computer only.

animeverse serve [--port 8000] [--open]
"""

import errno
import logging
import socket
import webbrowser

import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000
HOST = "127.0.0.1"  # never 0.0.0.0: other devices on the network can't reach the API


def serve(app: FastAPI, port: int = DEFAULT_PORT, open_browser: bool = False, has_ui: bool = False) -> int:
    """Serve until Ctrl+C. Returns an exit code: 0 stopped normally, 2 port busy."""
    # Bind the socket ourselves, so a busy port is a clear message and exit code 2
    # instead of uvicorn's generic failure.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, port))
    except OSError as exc:
        sock.close()
        if exc.errno == errno.EADDRINUSE:
            logger.error("Port %d is already in use (is another server running?). Try: --port %d", port, port + 1)
            return 2
        raise

    url = f"http://localhost:{port}/" if has_ui else f"http://localhost:{port}/v1/anime"
    if has_ui:
        logger.info("Serving the web UI at http://localhost:%d/ and the API at /v1/ (press Ctrl+C to stop)", port)
    else:
        logger.info("Serving the API at http://localhost:%d/v1/ (press Ctrl+C to stop)", port)
    if open_browser:
        webbrowser.open(url)
    server = uvicorn.Server(uvicorn.Config(app, log_level="info", server_header=False))
    server.run(sockets=[sock])
    return 0
