"""Application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Store runtime configuration.

    Args:
    -----
        No explicit arguments are required. Values are loaded from environment.

    Returns:
    --------
        Settings:
            Application settings instance.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://therecipe:change-me@localhost:5432/therecipe"
    )
    app_secret_key: str = "change-me"
    app_base_url: str = "http://localhost:8000"
    ai_provider: str = "disabled"
    openai_api_key: str = ""
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """
    Return cached application settings.

    Returns:
    --------
        Settings:
            Cached settings object.
    """

    return Settings()
