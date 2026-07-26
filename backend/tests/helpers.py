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
