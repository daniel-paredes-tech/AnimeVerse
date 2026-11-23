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
    for name in [
        *VALID_ENV,
        "POSTGRES_HOST",
        "POSTGRES_SSLMODE",
        "POSTGRES_CONNECT_TIMEOUT",
        "LOG_LEVEL",
        "OPENAPI_PATH",
        "WEB_DIST_DIR",
    ]:
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


def test_openapi_path_defaults_to_the_contract_in_the_current_folder(env, tmp_path):
    (tmp_path / "openapi.yaml").write_text("openapi: 3.1.0\n")
    env.chdir(tmp_path)

    assert config.load_openapi_path().name == "openapi.yaml"


def test_openapi_path_can_be_set_and_must_exist(env, tmp_path):
    contract = tmp_path / "contract.yaml"
    contract.write_text("openapi: 3.1.0\n")
    env.setenv("OPENAPI_PATH", str(contract))
    assert config.load_openapi_path() == contract

    env.setenv("OPENAPI_PATH", str(tmp_path / "missing.yaml"))
    with pytest.raises(config.ConfigError, match="not found"):
        config.load_openapi_path()


def test_web_dist_is_used_only_once_built(env, tmp_path):
    env.setenv("WEB_DIST_DIR", str(tmp_path / "dist"))
    assert config.load_web_dist() is None  # not built yet: the API is served alone

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<!doctype html>")
    assert config.load_web_dist() == tmp_path / "dist"
