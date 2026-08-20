"""Email verification and password reset.

Sending is never exercised here: `Settings.mail_configured` is false without
SMTP credentials, so `mail.send` appends to `mail.OUTBOX` instead of opening a
socket. The tests read the link out of that, which is also how a developer
completes a signup locally.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import authtokens, mail
from app.db import SessionLocal
from app.models import AuthToken, User

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def _fresh_limiter():
    """`email_limiter` is module-level in the router, so its 5/hour budget is
    shared by every test in this file and the seventh one would 429 for
    reasons that have nothing to do with what it is checking."""
    from app.routers.auth import email_limiter

    email_limiter.reset()
    yield
    email_limiter.reset()


def _link_token(message: mail.Message) -> str:
    m = re.search(r"token=([\w\-]+)", message.body)
    assert m, f"no token in message body:\n{message.body}"
    return m.group(1)


def _sent_to(email: str) -> list[mail.Message]:
    return [m for m in mail.OUTBOX if m.to == email]


async def _register(client, email: str, password: str = "password-123"):
    mail.OUTBOX.clear()
    r = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert r.status_code == 201, r.text
    return r


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

async def test_registration_does_not_grant_access(client):
    await _register(client, "unverified@example.com")
    r = await client.post(
        "/auth/login",
        json={"email": "unverified@example.com", "password": "password-123"},
    )
    assert r.status_code == 403


async def test_wrong_password_on_unverified_account_still_says_401(client):
    """The verification 403 must sit BEHIND the password check.

    In front of it, anyone could type an address and learn from the 403 that
    it had an account — without knowing the password. That is the enumeration
    hole the shared 401 wording exists to avoid.
    """
    await _register(client, "order@example.com")
    r = await client.post(
        "/auth/login", json={"email": "order@example.com", "password": "wrong-one"}
    )
    assert r.status_code == 401


async def test_verify_link_grants_access(client):
    await _register(client, "newbie@example.com")
    sent = _sent_to("newbie@example.com")
    assert len(sent) == 1

    r = await client.post(
        "/auth/verify/confirm", json={"token": _link_token(sent[0])}
    )
    assert r.status_code == 200
    assert r.json()["access_token"]

    r = await client.post(
        "/auth/login",
        json={"email": "newbie@example.com", "password": "password-123"},
    )
    assert r.status_code == 200


async def test_verification_link_is_single_use(client):
    await _register(client, "twice@example.com")
    token = _link_token(_sent_to("twice@example.com")[0])
    assert (await client.post("/auth/verify/confirm", json={"token": token})).status_code == 200
    assert (await client.post("/auth/verify/confirm", json={"token": token})).status_code == 400


async def test_garbage_and_expired_tokens_are_refused(client):
    assert (
        await client.post("/auth/verify/confirm", json={"token": "not-a-token"})
    ).status_code == 400

    await _register(client, "stale@example.com")
    token = _link_token(_sent_to("stale@example.com")[0])
    async with SessionLocal() as session:
        row = await session.scalar(
            select(AuthToken)
            .join(User, User.id == AuthToken.user_id)
            .where(User.email == "stale@example.com", AuthToken.kind == "verify")
        )
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()
    assert (
        await client.post("/auth/verify/confirm", json={"token": token})
    ).status_code == 400


async def test_a_reset_token_cannot_verify_an_address(client):
    """Kinds are not interchangeable. A reset link proves the same control of
    the mailbox, but accepting one here would mean any endpoint that mints a
    token can be replayed against any endpoint that consumes one."""
    await _register(client, "kinds@example.com")
    await client.post("/auth/password/forgot", json={"email": "kinds@example.com"})
    reset_token = _link_token(_sent_to("kinds@example.com")[-1])
    assert (
        await client.post("/auth/verify/confirm", json={"token": reset_token})
    ).status_code == 400


# ---------------------------------------------------------------------------
# Telling nobody anything
# ---------------------------------------------------------------------------

async def test_forgot_password_is_silent_about_unknown_addresses(client):
    mail.OUTBOX.clear()
    r = await client.post(
        "/auth/password/forgot", json={"email": "ghost@example.com"}
    )
    assert r.status_code == 200
    assert _sent_to("ghost@example.com") == []

    await _register(client, "real@example.com")
    mail.OUTBOX.clear()
    r2 = await client.post("/auth/password/forgot", json={"email": "real@example.com"})
    assert r2.status_code == 200
    # identical response for both; only the mailbox differs
    assert r2.json() == r.json()
    assert len(_sent_to("real@example.com")) == 1


async def test_resend_is_silent_for_already_verified_accounts(client):
    await _register(client, "done@example.com")
    token = _link_token(_sent_to("done@example.com")[0])
    await client.post("/auth/verify/confirm", json={"token": token})

    mail.OUTBOX.clear()
    r = await client.post("/auth/verify/resend", json={"email": "done@example.com"})
    assert r.status_code == 200
    assert _sent_to("done@example.com") == []


async def test_issuing_a_token_retires_the_previous_one(client):
    """Otherwise every resend leaves another working link alive, and a briefly
    exposed mailbox hands over all of them rather than one."""
    await _register(client, "resend@example.com")
    first = _link_token(_sent_to("resend@example.com")[0])
    await client.post("/auth/verify/resend", json={"email": "resend@example.com"})
    second = _link_token(_sent_to("resend@example.com")[-1])
    assert first != second

    assert (await client.post("/auth/verify/confirm", json={"token": first})).status_code == 400
    assert (await client.post("/auth/verify/confirm", json={"token": second})).status_code == 200


# ---------------------------------------------------------------------------
# Reset ends other sessions
# ---------------------------------------------------------------------------

async def test_reset_signs_out_tokens_issued_before_it(client):
    """The whole point of the reset. Stateless JWTs have no server-side list to
    revoke, so a token minted before `password_changed_at` must be refused —
    otherwise whoever prompted the reset keeps their session."""
    await _register(client, "victim@example.com")
    token = _link_token(_sent_to("victim@example.com")[0])
    await client.post("/auth/verify/confirm", json={"token": token})
    login = await client.post(
        "/auth/login",
        json={"email": "victim@example.com", "password": "password-123"},
    )
    old_jwt = login.json()["access_token"]
    old_auth = {"Authorization": f"Bearer {old_jwt}"}
    assert (await client.get("/me", headers=old_auth)).status_code == 200

    await client.post("/auth/password/forgot", json={"email": "victim@example.com"})
    reset_token = _link_token(_sent_to("victim@example.com")[-1])
    r = await client.post(
        "/auth/password/reset",
        json={"token": reset_token, "password": "brand-new-pass"},
    )
    assert r.status_code == 200

    # the pre-reset session is gone
    assert (await client.get("/me", headers=old_auth)).status_code == 401
    # the token handed back by the reset still works
    new_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get("/me", headers=new_auth)).status_code == 200


async def test_reset_changes_the_password(client):
    await _register(client, "changed@example.com")
    await client.post("/auth/verify/confirm", json={"token": _link_token(_sent_to("changed@example.com")[0])})
    await client.post("/auth/password/forgot", json={"email": "changed@example.com"})
    reset_token = _link_token(_sent_to("changed@example.com")[-1])
    await client.post(
        "/auth/password/reset",
        json={"token": reset_token, "password": "brand-new-pass"},
    )

    old = await client.post(
        "/auth/login",
        json={"email": "changed@example.com", "password": "password-123"},
    )
    assert old.status_code == 401
    new = await client.post(
        "/auth/login",
        json={"email": "changed@example.com", "password": "brand-new-pass"},
    )
    assert new.status_code == 200


async def test_reset_also_settles_verification(client):
    """Someone who never clicked the original link would otherwise reset their
    password and still be locked out, with no route forward. Reaching the
    mailbox proves the address either way."""
    await _register(client, "neverclicked@example.com")
    await client.post(
        "/auth/password/forgot", json={"email": "neverclicked@example.com"}
    )
    reset_token = _link_token(_sent_to("neverclicked@example.com")[-1])
    await client.post(
        "/auth/password/reset",
        json={"token": reset_token, "password": "brand-new-pass"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "neverclicked@example.com", "password": "brand-new-pass"},
    )
    assert r.status_code == 200


async def test_a_token_with_no_version_claim_is_refused(client):
    """Tokens predating this feature carry no `ver`, so nothing can place them
    against the account's counter. Treating a missing claim as current would
    exempt exactly the tokens a reset is meant to kill."""
    import jose.jwt as jose_jwt

    from app.config import get_settings
    from app.security import ALGORITHM

    await _register(client, "legacy@example.com")
    await client.post(
        "/auth/verify/confirm",
        json={"token": _link_token(_sent_to("legacy@example.com")[0])},
    )
    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.email == "legacy@example.com")
        )
        uid = user.id

    legacy = jose_jwt.encode(
        {"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )
    r = await client.get("/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 401


async def test_a_token_from_a_future_version_is_refused(client):
    """A version ahead of the row means the claim was forged or the row rolled
    back. `!=` rather than `<` so neither direction is trusted."""
    import jose.jwt as jose_jwt

    from app.config import get_settings
    from app.security import ALGORITHM

    await _register(client, "future@example.com")
    await client.post(
        "/auth/verify/confirm",
        json={"token": _link_token(_sent_to("future@example.com")[0])},
    )
    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.email == "future@example.com")
        )
        uid = user.id

    forged = jose_jwt.encode(
        {
            "sub": str(uid),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "ver": 99,
        },
        get_settings().secret_key,
        algorithm=ALGORITHM,
    )
    r = await client.get("/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

async def test_the_token_is_never_stored_in_the_clear(client):
    await _register(client, "storage@example.com")
    token = _link_token(_sent_to("storage@example.com")[0])
    async with SessionLocal() as session:
        rows = (await session.scalars(select(AuthToken))).all()
        stored = {r.token_hash for r in rows}
    assert token not in stored
    assert authtokens._digest(token) in stored
