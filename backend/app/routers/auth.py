import asyncio

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.demo import DemoUnavailable, mint_demo_user
from app.deps import CurrentUser, Session
from app.models import User
from app.ratelimit import SlidingWindowLimiter, client_key
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

# Generous for a person, restrictive for a script. A visitor might legitimately
# want a second clean portfolio after wrecking the first; nobody needs six an
# hour. Module-level so the budget survives across requests, which is the
# whole point — see app/ratelimit.py on why in-process is correct here.
demo_limiter = SlidingWindowLimiter(limit=5, window=3600)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, session: Session) -> User:
    email = payload.email.lower()
    # bcrypt is CPU-bound (~100ms by design) — keep it off the event loop
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=payload.display_name,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await session.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, session: Session) -> TokenOut:
    user = await session.scalar(
        select(User).where(User.email == payload.email.lower())
    )
    # identical error for unknown email and wrong password — leak nothing
    if user is None or not await asyncio.to_thread(
        verify_password, payload.password, user.password_hash
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Incorrect email or password"
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.post(
    "/auth/demo", response_model=TokenOut, status_code=status.HTTP_201_CREATED
)
async def create_demo_session(request: Request, session: Session) -> TokenOut:
    """Mint a private, disposable demo account and sign the caller straight in.

    No credentials in, a token out. That is the whole design: the shared
    account this replaces had its password compiled into the JS bundle, so
    every visitor edited the same portfolio and one of them could delete it.

    Unauthenticated and it writes, so two guards are load-bearing rather than
    decorative — the rate limit here, and the nightly purge in the scheduler.
    """
    if not get_settings().demo_enabled:
        # 404, not 403: on a deployment that has turned the demo off, the
        # endpoint may as well not exist. The frontend hides its button on
        # seeing this, so a private build self-configures.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo sign-in is not enabled")

    if not demo_limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many demo sessions from this address. Try again later.",
        )

    try:
        user = await mint_demo_user(session)
    except DemoUnavailable as exc:
        # 503 rather than 500: the database simply has not been seeded yet,
        # which is an operator's job and a condition that resolves itself the
        # moment they do it.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    await session.commit()
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
