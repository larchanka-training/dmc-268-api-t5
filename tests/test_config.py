from pathlib import Path

import pytest

from app.core.config import Settings, get_settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENV", "RELEASE_TAG", "REDIS_URL", "DATABASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.release_tag == "dev"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.database_url.get_secret_value() == ""
    assert settings.llm_api_key.get_secret_value() == ""


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RELEASE_TAG", "abc123")
    monkeypatch.setenv("REDIS_URL", "redis://dmc-redis:6379/1")

    settings = Settings(_env_file=None)

    assert settings.app_env == "staging"
    assert settings.release_tag == "abc123"
    assert settings.redis_url == "redis://dmc-redis:6379/1"


def test_reads_secret_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("DATABASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "database_url").write_text("postgresql://postgres:p%40ss@db/dmc")
    (tmp_path / "llm_api_key").write_text("sk-test")

    settings = Settings(_env_file=None, _secrets_dir=tmp_path)

    assert settings.database_url.get_secret_value() == (
        "postgresql://postgres:p%40ss@db/dmc"
    )
    assert settings.llm_api_key.get_secret_value() == "sk-test"


def test_secrets_are_masked_in_repr(tmp_path: Path) -> None:
    (tmp_path / "llm_api_key").write_text("sk-test")

    settings = Settings(_env_file=None, _secrets_dir=tmp_path)

    assert "sk-test" not in repr(settings)


def test_ignores_unknown_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNKNOWN_SETTING", "value")

    settings = Settings(_env_file=None)

    assert not hasattr(settings, "unknown_setting")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
