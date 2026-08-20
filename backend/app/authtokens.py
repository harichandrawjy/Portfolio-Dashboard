"""Single-use, expiring tokens for email verification and password reset.

The token is generated here, handed to the caller ONCE in plaintext so it can
go into an email, and stored only as a SHA-256 digest. Nothing can recover it
afterwards — a "resend" mints a new one rather than re-reading the old.

SHA-256, not bcrypt, and that is a deliberate departure from `security.py`.
Bcrypt's cost exists to slow dictionary attacks on human-chosen secrets;
these are 256 bits of `secrets.token_urlsafe`, where there is no dictionary
and brute force is hopeless regardless. Paying 100ms per lookup would only
hand an attacker a cheap way to saturate the reset endpoint.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthToken

VERIFY = "verify"
RESET = "reset"

# A verification link waits in an inbox, possibly overnight; a reset link is
# acted on immediately and is the more dangerous of the two if it lingers.
TTL = {VERIFY: timedelta(hours=24), RESET: timedelta(hours=1)}


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue(session: AsyncSession, user_id: uuid.UUID, kind: str) -> str:
    """Mint a token, retire the user's earlier unused ones of this kind, and
    return the plaintext — the only time it exists outside the recipient's
    inbox.

    Retiring the predecessors is what makes "resend" safe. Without it every
    request leaves another working link alive, so a mailbox that is briefly
    exposed hands over not one credential but every one ever issued.
    """
    now = datetime.now(timezone.utc)
    await session.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.kind == kind,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    token = secrets.token_urlsafe(32)
    session.add(
        AuthToken(
            user_id=user_id,
            kind=kind,
            token_hash=_digest(token),
            expires_at=now + TTL[kind],
        )
    )
    return token


async def consume(
    session: AsyncSession, token: str, kind: str
) -> uuid.UUID | None:
    """Redeem a token, returning the user id, or None if it is unusable.

    One return value for every failure — wrong, expired, already used, or of
    the other kind. The caller cannot tell them apart and neither can an
    attacker; "this link has already been used" is a confirmation that the
    account exists and that someone recently asked to reset it.

    Redemption is recorded before the caller acts on the result, so a
    double-submitted form cannot spend the same token twice.
    """
    row = await session.scalar(
        select(AuthToken).where(AuthToken.token_hash == _digest(token))
    )
    if row is None or row.kind != kind or row.used_at is not None:
        return None
    if row.expires_at <= datetime.now(timezone.utc):
        return None
    row.used_at = datetime.now(timezone.utc)
    return row.user_id
