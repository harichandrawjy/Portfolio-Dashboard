from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration; every value comes from the environment (or .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IDX Portfolio Dashboard"
    database_url: str  # required — no default so a missing env fails loudly


@lru_cache
def get_settings() -> Settings:
    return Settings()
