from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The value docker-compose.yml falls back to for local development. It is in a
# public repo, so a deployment that inherits it is signing JWTs with a key any
# reader already has — anyone could mint a token for any account.
DEV_SECRET_KEY = "dev-secret-change-me"

# Floor for a production signing key. `openssl rand -hex 32` gives 64 chars, so
# this only catches placeholders and typos, never a genuinely generated key.
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """App configuration; every value comes from the environment (or .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IDX Portfolio Dashboard"
    # "development" locally, "production" on a reachable box. Only used to
    # decide how strict the secret checks below are — everything else behaves
    # identically, so there is no second code path to keep in sync.
    app_env: str = "development"
    database_url: str  # required — no default so a missing env fails loudly
    idx_base_url: str = "https://www.idx.co.id"  # overridable for tests/failure drills
    secret_key: str  # JWT signing key — required, no default
    access_token_expire_minutes: int = 1440
    # POST /auth/demo mints a throwaway account with no authentication, which
    # is the point on a public showcase and unwanted on a private deployment.
    # Defaults on: the endpoint is rate-limited and its accounts are purged
    # nightly, and a demo nobody can reach is the more common mistake.
    demo_enabled: bool = True
    # Annual risk-free rate for Sharpe: Bank Indonesia policy rate (BI Rate).
    # A constant is fine for this project; update via env when BI moves it.
    risk_free_rate_annual: float = 0.055

    @model_validator(mode="after")
    def _reject_the_public_dev_key_in_production(self) -> "Settings":
        """Refuse to serve production traffic with a key from the repository.

        `secret_key` already has no default, so an unset variable fails loudly
        everywhere. This closes the other door: docker-compose.yml supplies
        `${SECRET_KEY:-dev-secret-change-me}` so a fresh clone runs with one
        command, and a deploy that forgets to override it would otherwise start
        perfectly happily while signing JWTs with a key published on GitHub —
        harmless on a laptop, total auth bypass on a reachable box.

        Gated on `app_env` rather than applied unconditionally, because the
        unconditional version broke `docker compose up` for everyone: the dev
        default IS the rejected value. A guard that stops local development is
        a guard people delete.
        """
        if self.app_env != "production":
            return self

        key = self.secret_key.strip()
        if key == DEV_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the development placeholder while "
                "APP_ENV=production. Generate a real one with "
                "`openssl rand -hex 32` and set it in the environment."
            )
        # A known key and a guessable one fail the same way. `str` alone
        # accepts "" and "abc123" quite happily, and an empty signing key is
        # worse than the placeholder it replaced — `openssl rand -hex 32`
        # yields 64 characters, so this floor rejects mistakes, not real keys.
        if len(key) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} "
                f"characters in production (got {len(key)}). Generate one with "
                "`openssl rand -hex 32`."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
