"""Command: import every configured franchise from AniList into PostgreSQL.

Run from the project root (the database must be running):

    .venv/bin/python -m animeverse.import_anime

Exit codes: 0 = all franchises imported, 1 = at least one franchise failed,
2 = the import could not start (missing settings or database unreachable).
"""

import logging
import sys

import psycopg

from animeverse.anilist_client import AniListClient
from animeverse.config import ConfigError, load_database_settings
from animeverse.importer import format_report, import_all
from animeverse.repository import connect

logger = logging.getLogger("animeverse.import_anime")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    try:
        settings = load_database_settings()
        conn = connect(settings)
    except ConfigError as exc:
        logger.error("Configuration problem: %s", exc)
        return 2
    except psycopg.OperationalError as exc:
        # psycopg's message names host, port and user, never the password.
        logger.error("Cannot connect to the database (is it running? 'docker compose ps'): %s", exc)
        return 2

    with conn, AniListClient() as client:
        reports = import_all(client, conn)

    print()
    print(format_report(reports))
    return 1 if any(r.failed for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
