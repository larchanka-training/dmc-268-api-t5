from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Swarm mounts secrets here as files (tmpfs); absent in local runs and tests.
SECRETS_DIR = Path("/run/secrets")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and secret files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None,
    )

    app_env: str = "local"
    release_tag: str = "dev"
    redis_url: str = "redis://localhost:6379/0"
    database_url: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    return Settings()
