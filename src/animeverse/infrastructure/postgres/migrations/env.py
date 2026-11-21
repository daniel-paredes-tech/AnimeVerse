"""Alembic's entry point: how to reach the database when running migrations.

The database settings come from the same place as the rest of AnimeVerse
(config.settings: environment variables or .env), never from alembic.ini,
so no password is written in any file. Code that runs migrations itself
(animeverse migrate, the tests) passes its settings in config.attributes.
"""

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL

from animeverse.config.settings import DatabaseSettings, load_database_settings


def database_url(settings: DatabaseSettings) -> URL:
    # URL.create escapes special characters in the password correctly.
    return URL.create(
        "postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.dbname,
    )


settings: DatabaseSettings = context.config.attributes.get("database_settings") or load_database_settings()

if context.is_offline_mode():
    # `alembic upgrade head --sql`: print the SQL instead of running it (useful to review a migration).
    context.configure(url=database_url(settings), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url(settings), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
