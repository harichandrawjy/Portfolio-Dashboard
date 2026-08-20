"""Password hashing (bcrypt) and JWT access tokens (python-jose)."""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # malformed stored hash
        return False


def create_access_token(user_id: uuid.UUID, token_version: int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        # `ver` is what lets a password reset end sessions it never saw. These
        # tokens are stateless, so there is no server-side list to revoke;
        # instead every token records the account's version at mint time, and
        # `deps` refuses any that no longer matches.
        {"sub": str(user_id), "exp": expire, "ver": token_version},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> tuple[uuid.UUID, int] | None:
    """Return `(user_id, token_version)`, or None for any invalid token.

    Returns the pair rather than just the id because the caller has to check
    the version against the user row; splitting that into a second decode
    would mean two places that must agree on how a token is read.

    A token with no `ver` is rejected. Those predate this claim, and treating
    a missing one as "current" would leave exactly the tokens a reset is meant
    to kill as the ones it cannot see.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        version = payload["ver"]
        if not isinstance(version, int):
            return None
        return uuid.UUID(payload["sub"]), version
    except (JWTError, KeyError, ValueError, TypeError):
        return None
