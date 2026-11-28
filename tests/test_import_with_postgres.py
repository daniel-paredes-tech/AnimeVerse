"""The import use case with the real PostgreSQL store (the source is faked: no network).

The unit tests in test_import_catalog.py cover the logic with in-memory
fakes; these check that the pieces really fit together. Made-up data only.
"""

from animeverse.application.import_catalog import ImportCatalog
from animeverse.application.ports import SearchResult
from animeverse.config.franchises import by_relations
from animeverse.domain.models import Anime
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import PostgresCatalogStore
from tests.fakes import FakeSource

NARUTO = by_relations("Naruto", search="Naruto", main_anilist_id=900001)
RESULTS = SearchResult(
    anime=[
        Anime(anilist_id=900001, title="NARUTO"),
        Anime(anilist_id=900002, title="NARUTO: Shippuuden"),
        Anime(anilist_id=900003, title="Onigiri"),
    ],
    rejected=[],
    relations={900001: frozenset({900002}), 900002: frozenset(), 900003: frozenset()},  # Onigiri: unrelated
)


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # fixed table names only


def test_importing_twice_creates_no_duplicates(committing_conn):
    use_case = ImportCatalog(FakeSource({"Naruto": RESULTS}), PostgresCatalogStore(committing_conn))

    first = use_case.import_franchise(NARUTO)
    second = use_case.import_franchise(NARUTO)

    assert (first.new, first.new_links) == (2, 2)
    assert (second.new, second.refreshed, second.new_links) == (0, 2, 0)
    assert (count(committing_conn, "franchises"), count(committing_conn, "anime")) == (1, 2)
    assert count(committing_conn, "anime_franchises") == 2


def test_import_commits_so_other_connections_see_the_data(committing_conn, test_db_settings):
    ImportCatalog(FakeSource({"Naruto": RESULTS}), PostgresCatalogStore(committing_conn)).import_franchise(NARUTO)

    with connect(test_db_settings) as other:
        assert count(other, "anime") == 2
