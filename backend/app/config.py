from functools import lru_cache
from urllib.parse import urlparse

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
    # Long-run equity risk premium — what holding the market is expected to
    # pay ABOVE the risk-free rate, used as E[Rm] = Rf + ERP in CAPM.
    #
    # An assumption, deliberately, rather than a measurement. The realised
    # figure is not usable as an expectation: over the windows available here
    # IHSG returned -18.9%/yr over one year, -7.5% over two and +1.1% over
    # five, so an estimate built from it says more about where the window
    # starts than about what equities are expected to pay. Worse, every one of
    # those is below the BI rate, which makes the premium negative and inverts
    # the model — CAPM then recommends minimising beta, and the "best return"
    # end of the frontier becomes whatever moves least with the market.
    #
    # 8% is a conventional emerging-market figure (a mature-market premium
    # around 4.5-5%, plus a country risk premium for Indonesia). It is a
    # number to argue with, which is why the panel shows it next to what the
    # index actually did.
    equity_risk_premium: float = 0.08

    # ── Outbound email ────────────────────────────────────────────────────
    # Gmail submission. Port 25 is blocked outbound on the Oracle Free Tier
    # box (verified: "Network is unreachable"), so direct-to-MX is not an
    # option and never will be — 587 and 465 are open and a relay is required.
    #
    # `smtp_password` is a Google App Password, not the account password:
    # Gmail refuses plain account passwords for SMTP, and an App Password can
    # be revoked on its own without touching the account.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Envelope sender. Empty means "use smtp_user", which is what Gmail
    # requires anyway — it rewrites From to the authenticated account, so a
    # different value here is silently ignored rather than honoured.
    mail_from: str = ""
    mail_from_name: str = "Arus"
    # Absolute origin used to build the links inside emails. It cannot be
    # derived from the request: a link built from a Host header is a
    # redirect-poisoning vector, and the emails are sent off the request path
    # anyway, where no request exists to read.
    app_base_url: str = "http://localhost:5173"

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    @property
    def mail_sender(self) -> str:
        return self.mail_from or self.smtp_user

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

        # Verification is mandatory, so unconfigured mail is not a degraded
        # feature — it is a locked front door. Every new registration would
        # be issued an account it can never sign into, and every forgotten
        # password would be unrecoverable. Fail at boot, where it is one
        # variable to fix, rather than at the first person who tries to join.
        if not self.mail_configured:
            raise ValueError(
                "SMTP_USER and SMTP_PASSWORD must be set while "
                "APP_ENV=production: email verification is required to sign "
                "in, so without them no new account can ever be used. Use a "
                "Google App Password, not the account password."
            )
        # Every verification and reset link is built from this. A wrong value
        # is not a broken page but an email nobody can act on, discovered by
        # the recipient rather than by us — so it is checked at boot.
        parsed = urlparse(self.app_base_url)
        # `hostname`, not `netloc`: urlparse("https://:80") yields a netloc of
        # ":80", which is truthy and would sail through. That is exactly the
        # value the DOMAIN-derived default produces on an IP-only box.
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(
                f"APP_BASE_URL is not a usable origin: {self.app_base_url!r}. "
                "It must look like https://arus.example.com. A common cause is "
                "DOMAIN being set to ':80' for an IP-only box, which makes the "
                "derived default 'https://:80' — set APP_BASE_URL explicitly "
                "in that case."
            )
        if parsed.hostname in ("localhost", "127.0.0.1"):
            raise ValueError(
                "APP_BASE_URL is still localhost while APP_ENV=production. "
                "Verification links would point at the recipient's own "
                "machine. Set it to the public origin."
            )

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
