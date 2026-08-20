"""Shared FastAPI dependencies. Every authenticated endpoint takes CurrentUser."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import decode_access_token

# auto_error=False so a missing header is a 401 (not HTTPBearer's 403)
bearer_scheme = HTTPBearer(auto_error=False)

Session = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Session,
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise unauthorized
    user_id, version = decoded
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized

    # A password reset bumps `token_version`, retiring every token minted
    # under the old one. Without this the reset would leave the attacker who
    # prompted it signed in until their token expired on its own — the one
    # window the feature exists to close.
    #
    # Equality, not `<`. A token from a FUTURE version is as wrong as a stale
    # one: it means the claim was tampered with or the row was rolled back,
    # and neither is a session to trust.
    if version != user.token_version:
        raise unauthorized

    # Defence in depth. `/auth/login` already refuses unverified accounts, so
    # no token should exist for one — this catches any future path that mints
    # a token without going through it. Demo accounts have synthetic addresses
    # and are exempt by design.
    if not user.is_demo and user.email_verified_at is None:
        raise unauthorized

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
