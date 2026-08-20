import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import authtokens, mail
from app.config import get_settings
from app.demo import DemoUnavailable, mint_demo_user
from app.deps import CurrentUser, Session
from app.models import User
from app.ratelimit import SlidingWindowLimiter, client_key
from app.scheduler import enqueue_email
from app.schemas import (
    AcceptedOut,
    EmailIn,
    LoginIn,
    PasswordResetIn,
    RegisterIn,
    TokenIn,
    TokenOut,
    UserOut,
)
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

# Generous for a person, restrictive for a script. A visitor might legitimately
# want a second clean portfolio after wrecking the first; nobody needs six an
# hour. Module-level so the budget survives across requests, which is the
# whole point — see app/ratelimit.py on why in-process is correct here.
demo_limiter = SlidingWindowLimiter(limit=5, window=3600)

# Anything that sends mail to a typed-in address. Tighter than the demo limit
# because the cost of abuse is someone else's inbox, not our database: without
# it the endpoints are a free relay for mailbombing any address an attacker
# picks, and Gmail's daily cap means that also takes the real system down.
email_limiter = SlidingWindowLimiter(limit=5, window=3600)


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
        # Flush, not commit: the token row needs the user's id, and both must
        # land together. A committed user with no token is an account nobody
        # can verify and, because the address is taken, nobody can re-register.
        await session.flush()
        token = await authtokens.issue(session, user.id, authtokens.VERIFY)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await session.refresh(user)

    # After the commit. Queuing first would risk emailing a link for a row that
    # then failed to save.
    enqueue_email(mail.verification_message(user.email, token, user.display_name))
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
    # 403, and only AFTER the password check. Reversing the order would tell
    # anyone who typed an address whether it had an account, without needing
    # the password — the enumeration hole the 401 above is worded to avoid.
    # The status is the frontend's cue to offer a resend; login returns 401 for
    # bad credentials and 403 only here, so it needs no message matching.
    if not user.is_demo and user.email_verified_at is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Confirm your email address before signing in. Check your inbox "
            "for the link, or request a new one.",
        )
    return TokenOut(access_token=create_access_token(user.id, user.token_version))


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
    return TokenOut(access_token=create_access_token(user.id, user.token_version))


@router.post("/auth/verify/confirm", response_model=TokenOut)
async def confirm_verification(payload: TokenIn, session: Session) -> TokenOut:
    """Redeem a verification link and sign the user straight in.

    Returning a token rather than a bare 204 is the difference between
    "verified, now go and log in" and being where you were trying to get. The
    link is single-use and already proves control of the address, which is a
    stronger claim than the password would make on its own.
    """
    user_id = await authtokens.consume(session, payload.token, authtokens.VERIFY)
    if user_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That link is invalid or has expired. Request a new one.",
        )
    user = await session.get(User, user_id)
    if user is None:  # account deleted between issue and redemption
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That link is no longer valid."
        )
    # Idempotent on purpose: a second click on a link already redeemed fails at
    # `consume` above, but a user verified by some other route should not be
    # stamped twice and have their original confirmation date overwritten.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
    await session.commit()
    return TokenOut(access_token=create_access_token(user.id, user.token_version))


@router.post("/auth/verify/resend", response_model=AcceptedOut)
async def resend_verification(
    payload: EmailIn, request: Request, session: Session
) -> AcceptedOut:
    """Send another verification link, if that address is waiting for one."""
    if not email_limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests from this address. Try again later.",
        )
    user = await session.scalar(
        select(User).where(User.email == payload.email.lower())
    )
    # Already-verified and never-existed take the same silent path as a real
    # resend. Anything else confirms whether an address is registered, and
    # whether its owner has got round to clicking the link.
    if user is not None and not user.is_demo and user.email_verified_at is None:
        token = await authtokens.issue(session, user.id, authtokens.VERIFY)
        await session.commit()
        enqueue_email(
            mail.verification_message(user.email, token, user.display_name)
        )
    return AcceptedOut()


@router.post("/auth/password/forgot", response_model=AcceptedOut)
async def forgot_password(
    payload: EmailIn, request: Request, session: Session
) -> AcceptedOut:
    """Start a password reset. Always answers the same way."""
    if not email_limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many requests from this address. Try again later.",
        )
    user = await session.scalar(
        select(User).where(User.email == payload.email.lower())
    )
    # Unverified accounts are eligible: someone who mistyped their password at
    # signup and never got in is exactly who needs this. Demo accounts are not
    # — their addresses are synthetic and their passwords unusable by design.
    if user is not None and not user.is_demo:
        token = await authtokens.issue(session, user.id, authtokens.RESET)
        await session.commit()
        enqueue_email(mail.reset_message(user.email, token, user.display_name))
    return AcceptedOut()


@router.post("/auth/password/reset", response_model=TokenOut)
async def reset_password(payload: PasswordResetIn, session: Session) -> TokenOut:
    """Set a new password from a reset link, and sign every other device out."""
    user_id = await authtokens.consume(session, payload.token, authtokens.RESET)
    if user_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That link is invalid or has expired. Request a new one.",
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That link is no longer valid."
        )

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user.password_hash = password_hash
    # Retires every token minted under the old version — see
    # `get_current_user`. This is the line that makes the reset end the
    # sessions the server never recorded.
    user.token_version += 1
    # Reaching the mailbox proves the address, so a reset settles verification
    # too. Otherwise someone who never clicked the original link resets their
    # password and is still locked out, with no obvious way forward.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
    await session.commit()

    # Minted from the bumped version, so it survives the sweep it just caused.
    return TokenOut(access_token=create_access_token(user.id, user.token_version))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
