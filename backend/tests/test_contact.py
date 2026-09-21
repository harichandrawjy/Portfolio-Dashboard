"""The public contact form.

The only unauthenticated write in the app, so most of what is worth testing
here is what it refuses rather than what it accepts.

Sending is never exercised: `Settings.mail_configured` is false without SMTP
credentials, so `mail.send` appends to `mail.OUTBOX` instead of opening a
socket.
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app import mail
from app.db import SessionLocal
from app.models import ContactMessage

pytestmark = pytest.mark.asyncio(loop_scope="session")

GOOD = {
    "name": "Rina Halim",
    "email": "Rina.Halim@Example.com",
    "topic": "consulting",
    "organisation": "PT Sumber Makmur",
    "message": "We would like to discuss an investment review for our treasury.",
}


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def _clean():
    """`contact_limiter` is module-level in the router, so its 3/hour budget is
    shared by every test in this file and the fourth would 429 for reasons
    that have nothing to do with what it is checking."""
    from app.routers.contact import contact_limiter

    contact_limiter.reset()
    mail.OUTBOX.clear()
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(delete(ContactMessage))
    yield
    contact_limiter.reset()
    mail.OUTBOX.clear()


async def _rows() -> list[ContactMessage]:
    async with SessionLocal() as session:
        return list(
            (await session.scalars(select(ContactMessage))).all()
        )


async def _count() -> int:
    async with SessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(ContactMessage))


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------

async def test_a_message_is_stored_and_announced(client):
    r = await client.post("/contact", json=GOOD)
    assert r.status_code == 202, r.text

    rows = await _rows()
    assert len(rows) == 1
    assert rows[0].name == "Rina Halim"
    assert rows[0].email == "rina.halim@example.com"  # normalised
    assert rows[0].topic == "consulting"
    assert rows[0].organisation == "PT Sumber Makmur"
    assert "treasury" in rows[0].message

    assert len(mail.OUTBOX) == 1
    assert GOOD["message"] in mail.OUTBOX[0].body


async def test_the_notification_replies_to_the_sender(client):
    """The address goes in Reply-To, never in From. From is the authenticated
    mailbox; forging the sender's domain there is what SPF and DMARC exist to
    refuse, and the message would be filed as spam or rejected outright."""
    await client.post("/contact", json=GOOD)
    assert mail.OUTBOX[0].reply_to == "rina.halim@example.com"
    assert mail.OUTBOX[0].to != "rina.halim@example.com"


async def test_no_line_break_can_reach_a_header(client):
    """Header injection needs a line break — that is the whole mechanism, and
    the only thing worth asserting here.

    The words survive: "Rina\\nBcc: x@y" becomes "Rina Bcc: x@y", which is a
    silly name and nothing more. Stripping the text too would be theatre, and
    would mangle honest names to no purpose. Python's email package does raise
    on a header containing a newline, but a 500 is a poor way to learn that
    someone pasted a line break into a form anyone can post to.
    """
    await client.post(
        "/contact",
        json={**GOOD, "name": "Rina\r\nBcc: someone@evil.example"},
    )
    subject = mail.OUTBOX[0].subject
    assert "\n" not in subject and "\r" not in subject
    assert "Rina Bcc: someone@evil.example" in subject


async def test_the_topic_leads_the_subject_line(client):
    """Consulting enquiries and bug reports want different attention, so the
    difference has to be visible in the inbox before either is opened."""
    await client.post("/contact", json=GOOD)
    assert mail.OUTBOX[0].subject.startswith("[Consulting] ")
    assert "PT Sumber Makmur" in mail.OUTBOX[0].subject

    from app.routers.contact import contact_limiter

    contact_limiter.reset()
    mail.OUTBOX.clear()
    await client.post(
        "/contact",
        json={**GOOD, "topic": "platform", "organisation": None},
    )
    assert mail.OUTBOX[0].subject.startswith("[Platform] ")
    # no organisation, so nothing is appended in parentheses
    assert "(" not in mail.OUTBOX[0].subject


async def test_an_individual_may_leave_the_organisation_out(client):
    """The page serves individuals as well as companies. A required company
    field would make an individual either invent one or leave."""
    body = {k: v for k, v in GOOD.items() if k != "organisation"}
    r = await client.post("/contact", json=body)
    assert r.status_code == 202, r.text
    rows = await _rows()
    assert rows[0].organisation is None


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------

async def test_the_honeypot_is_answered_with_success(client):
    """A bot that fills every field gets the same 202 a person gets. An error
    would tell it which field to leave alone next time."""
    good = await client.post("/contact", json=GOOD)
    from app.routers.contact import contact_limiter

    contact_limiter.reset()
    mail.OUTBOX.clear()
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(delete(ContactMessage))

    trapped = await client.post(
        "/contact", json={**GOOD, "website": "http://spam.example"}
    )
    assert trapped.status_code == good.status_code == 202
    assert trapped.json() == good.json()
    # ...but nothing happened
    assert await _count() == 0
    assert mail.OUTBOX == []


async def test_a_fourth_message_in_an_hour_is_refused(client):
    for i in range(3):
        r = await client.post(
            "/contact", json={**GOOD, "message": f"Message number {i} about Arus."}
        )
        assert r.status_code == 202, r.text

    r = await client.post("/contact", json={**GOOD, "message": "One more thing here."})
    assert r.status_code == 429
    assert await _count() == 3  # the refused one left no trace


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "not-an-address"),
        ("message", "too short"),           # min_length=10
        ("message", "x" * 4001),            # max_length=4000
        ("name", ""),                       # min_length=1
        ("name", "x" * 101),                # max_length=100
        ("email", "x" * 250 + "@example.com"),  # 254-char cap, matching the CHECK
        ("topic", "career"),                # not one of the three services
        ("topic", ""),
        ("organisation", "x" * 151),        # 150-char cap, matching the CHECK
    ],
)
async def test_bounds_are_enforced_as_422_not_500(client, field, value):
    """Every bound is stated twice — in `ContactIn` and as a CHECK constraint
    in migration 0010. These pin that the request layer catches them first, so
    a bad submission is a 422 about the field rather than a database error."""
    r = await client.post("/contact", json={**GOOD, field: value})
    assert r.status_code == 422, f"{field}={value!r} gave {r.status_code}"
    assert await _count() == 0
