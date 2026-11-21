"""Shared pytest setup for tests that need PostgreSQL.

Tests never touch the main database. They use a separate database named
"<POSTGRES_DB>_test" in the same container, which is created if missing and
rebuilt from db/schema.sql at the start of every test run.
"""

import dataclasses
from pathlib import Path

import pytest
from psycopg import sql

from animeverse.config.settings import load_database_settings
from animeverse.repository import connect

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


@pytest.fixture(scope="session")
def test_db_settings():
    """Settings for the test database, created fresh once per test run."""
    main = load_database_settings()
    test = dataclasses.replace(main, dbname=f"{main.dbname}_test")

    # Safety guard: the schema reset below deletes everything in the database.
    if not test.dbname.endswith("_test"):
        raise RuntimeError(f"Refusing to reset {test.dbname!r}: not a test database.")

    # CREATE DATABASE cannot run inside a transaction, hence autocommit.
    with connect(main) as conn:
        conn.autocommit = True
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test.dbname,)).fetchone()
        if not exists:
            # A database name is an identifier, not a value, so it can't be a
            # %s parameter. sql.Identifier quotes it safely instead.
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test.dbname)))

    # Drop everything and re-apply the current schema.
    with connect(test) as conn:
        conn.autocommit = True
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(SCHEMA_FILE.read_text())

    return test


@pytest.fixture
def conn(test_db_settings):
    """A connection whose changes are rolled back after each test."""
    connection = connect(test_db_settings)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture
def committing_conn(test_db_settings):
    """For code that commits itself (like the importer), so rollback can't undo it.

    Instead, every table is emptied before and after the test.
    """
    connection = connect(test_db_settings)

    def empty_tables():
        connection.execute("TRUNCATE anime_franchises, anime, franchises RESTART IDENTITY")
        connection.commit()

    empty_tables()
    try:
        yield connection
    finally:
        connection.rollback()  # in case the test left a failed transaction open
        empty_tables()
        connection.close()


@pytest.fixture
def count_rows(conn):
    """Helper: count the rows in a table."""

    def _count(table: str) -> int:
        query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
        return conn.execute(query).fetchone()[0]

    return _count
