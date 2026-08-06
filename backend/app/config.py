from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value docker-compose.yml falls back to for local development. It is in a
# public repo, so a deployment that inherits it is signing JWTs with a key any
# reader already has — anyone could mint a token for any account.
DEV_SECRET_KEY = "dev-secret-change-me"


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

    @field_validator("secret_key")
    @classmethod
    def _reject_the_public_dev_key(cls, v: str) -> str:
        """Fail to boot rather than serve with a key from the repository.

        `secret_key` already has no default, so an unset variable fails loudly.
        This closes the other door: docker-compose.yml supplies
        `${SECRET_KEY:-dev-secret-change-me}` for local work, and a deploy that
        forgets to override it would start perfectly happily with a signing key
        that is published on GitHub. Harmless on a laptop, total auth bypass the
        moment the box is reachable.
        """
        if v.strip() == DEV_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the development placeholder. Generate a "
                "real one with `openssl rand -hex 32` and set it in the "
                "environment before starting."
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
