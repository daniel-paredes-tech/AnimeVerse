"""The `animeverse` command, and the composition root.

    animeverse import            import every configured franchise from AniList
    animeverse serve [--open]    private, read-only local page at http://localhost:8000

This is the only module that chooses concrete implementations: AniList as
the data source, PostgreSQL as the store. Swapping either one (another API,
a database in the cloud) means changing the wiring here, not the use cases.

Exit codes: 0 = success, 1 = at least one franchise failed,
2 = could not start (missing settings, database unreachable, port busy).
"""

import argparse
import logging
from collections.abc import Sequence

from animeverse.application.import_catalog import ImportCatalog
from animeverse.application.ports import StoreUnavailable
from animeverse.config.franchises import FRANCHISES
from animeverse.config.settings import ConfigError, DatabaseSettings, load_database_settings
from animeverse.entrypoints.report import format_report
from animeverse.entrypoints.web.server import DEFAULT_PORT, serve
from animeverse.infrastructure.anilist.client import AniListClient
from animeverse.infrastructure.anilist.source import AniListSource
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import PostgresCatalogReader, PostgresCatalogStore

logger = logging.getLogger("animeverse")

EXIT_OK, EXIT_FAILED, EXIT_CANNOT_START = 0, 1, 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="animeverse", description="Anime from AniList, stored in PostgreSQL.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("import", help="import every configured franchise from AniList")
    serve_parser = commands.add_parser("serve", help="private, read-only local page with the stored data")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to use (default {DEFAULT_PORT})")
    serve_parser.add_argument("--open", action="store_true", help="open the page in your default browser")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    try:
        settings = load_database_settings()
    except ConfigError as exc:
        logger.error("Configuration problem: %s", exc)
        return EXIT_CANNOT_START

    if args.command == "import":
        return run_import(settings)
    return serve(PostgresCatalogReader(lambda: connect(settings)), port=args.port, open_browser=args.open)


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
