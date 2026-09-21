"""The public contact page's one endpoint.

Arus offers consulting and market research alongside the tracker itself, so a
message here may be a prospective client rather than a bug report. `topic` is
what separates them, and it leads the notification's subject line so the two
can be told apart before either is opened.

This is the only handler in the app that writes to the database without
anyone being signed in, which is the whole design problem: a form that both
stores a row and causes an email is exactly what a spam bot is looking for.
Three cheap defences, in the order they run:

1. A honeypot field, answered with success rather than an error. Telling a
   bot it failed only teaches it which field to leave alone next time.
2. A sliding-window limit per caller, tighter than the auth one — nobody has
   three different things to say in an hour, whereas a resend genuinely can
   be needed a few times.
3. Length caps, stated in `ContactIn` and again as CHECK constraints in
   migration 0010.

Notably absent is a CAPTCHA. It would mean a third-party script on a page
that otherwise loads nothing external, and the traffic here does not justify
it. If that changes, the limiter is where to look first.
"""

from fastapi import APIRouter, HTTPException, Request, status

from app import mail
from app.deps import Session
from app.models import ContactMessage
from app.ratelimit import SlidingWindowLimiter, client_key
from app.scheduler import enqueue_email
from app.schemas import ContactAcceptedOut, ContactIn

router = APIRouter(tags=["contact"])

# Three an hour per address. The auth limiter allows five because a person
# waiting on a verification link has a real reason to ask again; nobody has
# three unrelated things to say to a portfolio project in an hour.
contact_limiter = SlidingWindowLimiter(limit=3, window=3600)


@router.post(
    "/contact",
    response_model=ContactAcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_contact(
    payload: ContactIn, request: Request, session: Session
) -> ContactAcceptedOut:
    """Store a message, then ask the scheduler to announce it.

    202 rather than 201: what the caller gets back is a promise that the
    message was accepted, not that anyone has read it. The email may still be
    sitting in the scheduler's queue when this returns, which is the point of
    enqueuing it (architecture decision 4 — request handlers never call an
    external API, and a handler that waits on SMTP times its own response).
    """
    if payload.website:
        # Honeypot tripped. Identical response to the happy path, and no row,
        # no email, and no rate-limit spend — a bot that hammers this costs
        # nothing and learns nothing.
        return ContactAcceptedOut()

    if not contact_limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many messages in a short time. Try again in an hour, or "
            "email aruscapitalteam@gmail.com.",
        )

    org = (payload.organisation or "").strip() or None
    session.add(
        ContactMessage(
            name=payload.name.strip(),
            email=payload.email.lower(),
            topic=payload.topic,
            organisation=org,
            message=payload.message.strip(),
        )
    )
    # Commit BEFORE enqueuing. The row is the record and the mail is a nudge,
    # so a message must survive the nudge failing.
    await session.commit()

    enqueue_email(
        mail.contact_notification(
            payload.name.strip(),
            payload.email.lower(),
            payload.message.strip(),
            topic=payload.topic,
            organisation=org,
        )
    )
    return ContactAcceptedOut()
