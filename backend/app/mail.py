"""Outbound email: message construction (pure) and SMTP delivery (not).

The split is deliberate and matches the rest of the codebase — `analytics`,
`optimize` and `pnl` are all pure functions with a thin caller. Building a
message is pure and unit-tested against exact strings; putting it on the wire
is a side effect with a socket, and nothing else in here depends on it.

Delivery is SYNCHRONOUS by design. smtplib is blocking, so this module is
always called through `asyncio.to_thread` from the scheduler — never from a
request handler. That is architecture decision 4 ("request handlers never
call an external API") and it is not a formality here: a handler that waits
on Gmail leaks a timing signal for whether an address exists, which is the
one thing `/auth/password/forgot` exists to hide.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str


# When SMTP is unconfigured — every test, and local development — messages
# land here instead of on the wire, and the link is logged so a developer can
# complete a signup without a mail server. Production cannot reach this path:
# `Settings` refuses to boot without SMTP credentials when APP_ENV=production.
OUTBOX: list[Message] = []


def verification_message(to: str, token: str, display_name: str | None) -> Message:
    settings = get_settings()
    who = display_name or to
    link = f"{settings.app_base_url.rstrip('/')}/verify?token={token}"
    return Message(
        to=to,
        subject="Confirm your Arus address",
        body=(
            f"Hello {who},\n\n"
            "Confirm this address to finish setting up your Arus account:\n\n"
            f"{link}\n\n"
            "The link works once and expires in 24 hours.\n\n"
            "If you did not create an account, ignore this message — the "
            "address cannot be used until someone follows the link.\n\n"
            "Arus tracks mock IDX portfolios. No real money moves through it."
        ),
    )


def reset_message(to: str, token: str, display_name: str | None) -> Message:
    settings = get_settings()
    who = display_name or to
    link = f"{settings.app_base_url.rstrip('/')}/reset?token={token}"
    return Message(
        to=to,
        subject="Reset your Arus password",
        body=(
            f"Hello {who},\n\n"
            "Someone asked to reset the password on this account:\n\n"
            f"{link}\n\n"
            "The link works once and expires in one hour. Using it signs out "
            "every device currently on the account.\n\n"
            "If this was not you, no action is needed — the password is "
            "unchanged until someone follows the link."
        ),
    )


def send(message: Message) -> None:
    """Deliver one message. Blocking; call via `asyncio.to_thread`."""
    settings = get_settings()

    if not settings.mail_configured:
        OUTBOX.append(message)
        logger.warning(
            "SMTP not configured — message to %s not sent. Body:\n%s",
            message.to, message.body,
        )
        return

    msg = EmailMessage()
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_sender))
    msg["To"] = message.to
    msg["Subject"] = message.subject
    msg.set_content(message.body)

    # STARTTLS on 587 rather than implicit TLS on 465. Both are open from the
    # box, but 587 is the submission port Gmail documents, and starting in the
    # clear here is safe only because `starttls` below is unconditional — if
    # the upgrade fails smtplib raises, and nothing is sent in plaintext.
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    logger.info("sent %r to %s", message.subject, message.to)
