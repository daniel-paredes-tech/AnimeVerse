"""Tests for the `animeverse` command: start-up failures give exit code 2."""

import dataclasses

import pytest

from animeverse.config.settings import ConfigError
from animeverse.entrypoints import cli


def test_missing_settings_give_exit_code_2(monkeypatch, caplog):
    def missing():
        raise ConfigError("Missing required setting POSTGRES_PASSWORD.")

    monkeypatch.setattr(cli, "load_database_settings", missing)

    assert cli.main(["import"]) == 2
    assert "POSTGRES_PASSWORD" in caplog.text


def test_unreachable_database_gives_exit_code_2(test_db_settings, caplog):
    unreachable = dataclasses.replace(test_db_settings, port=1)  # nothing listens on port 1

    assert cli.run_import(unreachable) == 2
    assert "Cannot connect to the database" in caplog.text


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


def test_migrate_with_unreachable_database_gives_exit_code_2(test_db_settings, caplog):
    unreachable = dataclasses.replace(test_db_settings, port=1)

    assert cli.run_migrate(unreachable) == 2
    assert "Cannot connect to the database" in caplog.text
