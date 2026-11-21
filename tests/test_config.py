"""Tests for animeverse.config. No database or .env file needed."""

import pytest

from animeverse.config import settings as config

VALID_ENV = {
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "super-secret-password",
    "POSTGRES_DB": "db",
    "POSTGRES_PORT": "5433",
}


@pytest.fixture
def env(monkeypatch):
    """Use only the variables set by each test: ignore .env and the real environment."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    for name in [*VALID_ENV, "POSTGRES_HOST", "POSTGRES_SSLMODE", "POSTGRES_CONNECT_TIMEOUT", "LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_missing_setting_raises_clear_error(env):
    env.delenv("POSTGRES_PASSWORD")

    with pytest.raises(config.ConfigError, match="POSTGRES_PASSWORD"):
        config.load_database_settings()


def test_non_numeric_port_raises_clear_error(env):
    env.setenv("POSTGRES_PORT", "abc")

    with pytest.raises(config.ConfigError, match="POSTGRES_PORT"):
        config.load_database_settings()


def test_password_is_hidden_when_settings_are_printed(env):
    settings = config.load_database_settings()

    assert settings.port == 5433
    assert settings.host == "localhost"
    assert "super-secret-password" not in repr(settings)
    assert "super-secret-password" not in str(settings)


def test_optional_settings_have_safe_defaults(env):
    settings = config.load_database_settings()

    assert (settings.sslmode, settings.connect_timeout) == ("prefer", 10)
    assert config.load_log_level() == "INFO"


def test_cloud_settings_are_read(env):
    env.setenv("POSTGRES_HOST", "db.example.internal")
    env.setenv("POSTGRES_SSLMODE", "require")
    env.setenv("POSTGRES_CONNECT_TIMEOUT", "5")

    settings = config.load_database_settings()

    assert (settings.host, settings.sslmode, settings.connect_timeout) == ("db.example.internal", "require", 5)


@pytest.mark.parametrize(
    ("name", "value"),
    [("POSTGRES_SSLMODE", "yes"), ("POSTGRES_CONNECT_TIMEOUT", "0"), ("POSTGRES_PORT", "-1"), ("LOG_LEVEL", "LOUD")],
)
def test_invalid_values_raise_clear_errors(env, name, value):
    env.setenv(name, value)

    with pytest.raises(config.ConfigError, match=name):
        config.load_database_settings()
        config.load_log_level()
