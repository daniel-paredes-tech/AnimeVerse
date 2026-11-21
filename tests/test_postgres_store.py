"""Tests for the PostgreSQL adapter's error translation (the rest is in the contract tests)."""

import psycopg
import pytest

from animeverse.application.ports import StoreUnavailable
from animeverse.domain.models import Franchise
from animeverse.infrastructure.postgres.connection import connect
from animeverse.infrastructure.postgres.store import PostgresCatalogReader, PostgresCatalogStore


def test_unreachable_database_becomes_store_unavailable():
    def refuse() -> psycopg.Connection:
        raise psycopg.OperationalError("connection refused")

    with pytest.raises(StoreUnavailable, match="connection refused"):
        PostgresCatalogReader(refuse).anime_by_franchise()


def test_lost_connection_becomes_store_unavailable(test_db_settings):
    conn = connect(test_db_settings)
    conn.close()  # as if the server had gone away

    with pytest.raises(StoreUnavailable), PostgresCatalogStore(conn).session() as session:
        session.save_franchise(Franchise("Naruto", "Naruto"))
