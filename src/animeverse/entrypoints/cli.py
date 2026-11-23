"""The `animeverse` command, and the composition root.

    animeverse migrate           bring the database schema up to date (run it first)
    animeverse import            import every configured franchise from AniList
    animeverse serve [--open]    the REST API at http://localhost:8000/v1/ (this computer only)

This is the only module that chooses concrete implementations: AniList as
the data source, PostgreSQL as the store. Swapping either one (another API,
a database in the cloud) means changing the wiring here, not the use cases.

Exit codes: 0 = success, 1 = at least one franchise failed,
2 = could not start (missing settings or contract file, database unreachable, port busy).
`migrate` returns 0 or 2.
"""

import argparse
import logging
from collections.abc import Sequence

import psycopg

from animeverse.application.catalog import BrowseCatalog
from animeverse.application.import_catalog import ImportCatalog
from animeverse.application.ports import StoreUnavailable
from animeverse.application.watchlist import ManageWatchlist
from animeverse.config.franchises import FRANCHISES
from animeverse.config.settings import (
    ConfigError,
    DatabaseSettings,
    load_database_settings,
    load_log_level,
    load_openapi_path,
)
from animeverse.entrypoints.api.app import create_app
from animeverse.entrypoints.api.server import DEFAULT_PORT, serve
from animeverse.entrypoints.report import format_report
from animeverse.infrastructure.anilist.client import AniListClient
from animeverse.infrastructure.anilist.source import AniListSource
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.migrate import upgrade_to_latest
from animeverse.infrastructure.postgres.store import (
    PostgresCatalogQuery,
    PostgresCatalogStore,
    PostgresWatchlistStore,
)

logger = logging.getLogger("animeverse")

EXIT_OK, EXIT_FAILED, EXIT_CANNOT_START = 0, 1, 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="animeverse", description="Anime from AniList, stored in PostgreSQL.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="bring the database schema up to date")
    commands.add_parser("import", help="import every configured franchise from AniList")
    serve_parser = commands.add_parser("serve", help="the REST API, on this computer only")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to use (default {DEFAULT_PORT})")
    serve_parser.add_argument("--open", action="store_true", help="open the API in your default browser")
    args = parser.parse_args(argv)

    logging.basicConfig(format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        logging.getLogger().setLevel(load_log_level())
        settings = load_database_settings()
    except ConfigError as exc:
        logger.error("Configuration problem: %s", exc)
        return EXIT_CANNOT_START

    if args.command == "migrate":
        return run_migrate(settings)
    if args.command == "import":
        return run_import(settings)
    return run_serve(settings, port=args.port, open_browser=args.open)


def run_migrate(settings: DatabaseSettings) -> int:
    try:
        upgrade_to_latest(settings)
    except StoreUnavailable as exc:
        logger.error("Cannot connect to the database (is it running? 'docker compose ps'): %s", exc)
        return EXIT_CANNOT_START
    logger.info("Database schema is up to date.")
    return EXIT_OK


def run_serve(settings: DatabaseSettings, port: int, open_browser: bool) -> int:
    """Wire the API to PostgreSQL and serve it.

    The database is not checked here: while it is down, every request is
    answered with a 503 problem explaining it, and it works again as soon as
    the database is back.
    """
    try:
        contract = load_openapi_path().read_bytes()
    except ConfigError as exc:
        logger.error("Configuration problem: %s", exc)
        return EXIT_CANNOT_START

    def open_connection() -> psycopg.Connection:
        return connect(settings)

    query = PostgresCatalogQuery(open_connection)
    app = create_app(BrowseCatalog(query), ManageWatchlist(query, PostgresWatchlistStore(open_connection)), contract)
    return serve(app, port=port, open_browser=open_browser)


def run_import(settings: DatabaseSettings) -> int:
    try:
        conn = connect(settings)
    except StoreUnavailable as exc:
        logger.error("Cannot connect to the database (is it running? 'docker compose ps'): %s", exc)
        return EXIT_CANNOT_START

    with conn, AniListClient() as client:
        use_case = ImportCatalog(AniListSource(client), PostgresCatalogStore(conn))
        reports = use_case.run(FRANCHISES)

    print()
    print(format_report(reports))
    return EXIT_FAILED if any(r.failed for r in reports) else EXIT_OK
