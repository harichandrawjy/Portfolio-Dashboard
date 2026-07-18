from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration; every value comes from the environment (or .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IDX Portfolio Dashboard"
    database_url: str  # required — no default so a missing env fails loudly
    idx_base_url: str = "https://www.idx.co.id"  # overridable for tests/failure drills
    secret_key: str  # JWT signing key — required, no default
    access_token_expire_minutes: int = 1440
    # Annual risk-free rate for Sharpe: Bank Indonesia policy rate (BI Rate).
    # A constant is fine for this project; update via env when BI moves it.
    risk_free_rate_annual: float = 0.055


@lru_cache
def get_settings() -> Settings:
    return Settings()
