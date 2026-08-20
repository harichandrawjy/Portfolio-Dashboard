"""Shared test helpers."""

# Buys are always checked against the cash balance, so any portfolio that
# trades in a test has to be funded first. Backdated well before every
# fixture trade date, because only trades on or after the first cash flow
# count towards the balance.
FUNDING_DATE = "2026-01-01"
DEFAULT_FUNDING = 10_000_000_000


async def fund(client, auth, pid, amount: int = DEFAULT_FUNDING):
    """Deposit cash into a portfolio so its buys are affordable."""
    return await client.post(
        f"/portfolios/{pid}/cash",
        json={"type": "DEPOSIT", "amount": amount, "occurred_at": FUNDING_DATE},
        headers=auth,
    )


async def funded_portfolio(client, auth, name: str, **body) -> str:
    """Create a funded portfolio and return its id."""
    r = await client.post("/portfolios", json={"name": name, **body}, headers=auth)
    pid = r.json()["id"]
    await fund(client, auth, pid)
    return pid


# Since migration 0009 an address must be confirmed before /auth/login will
# issue a token, so "register then log in" no longer works anywhere. Every
# test file used to carry its own copy of that two-step helper; this is the
# one place that knows about the third step.
#
# The link is read out of `mail.OUTBOX`, which is where `mail.send` puts
# messages when SMTP is unconfigured — the case in every test.
async def register_verified(client, email: str, password: str) -> dict:
    """Register, confirm the address, and return Authorization headers."""
    import re

    from app import mail

    r = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    if r.status_code == 409:
        # Several tests sign in repeatedly as the same address, and the suite
        # shares one database for the whole session. The account already
        # exists and was verified the first time round, so log in normally.
        r = await client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    sent = [m for m in mail.OUTBOX if m.to == email.lower()]
    assert sent, f"no verification email queued for {email}"
    token = re.search(r"token=([\w\-]+)", sent[-1].body).group(1)

    # Confirming hands back a token directly, so there is no second login —
    # which also keeps these helpers one round trip cheaper than before.
    r = await client.post("/auth/verify/confirm", json={"token": token})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
