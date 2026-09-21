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
from html import escape
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str
    #: The same content as `body`, marked up. Sent as the richer half of a
    #: multipart/alternative — see `send` for why a lone text/plain part is a
    #: deliverability problem rather than a stylistic choice.
    html: str = ""
    #: Where a reply should go when that is not the sending mailbox. Set for
    #: contact-form notifications so answering someone is one keystroke
    #: rather than a copy-paste out of the body.
    reply_to: str = ""


# When SMTP is unconfigured — every test, and local development — messages
# land here instead of on the wire, and the link is logged so a developer can
# complete a signup without a mail server. Production cannot reach this path:
# `Settings` refuses to boot without SMTP credentials when APP_ENV=production.
OUTBOX: list[Message] = []


def _html(who: str, lead: str, link: str, action: str, note: str) -> str:
    """The markup half of a message.

    Inline styles only, no images, no tracking pixel, no external stylesheet:
    every one of those is a spam signal, and a remote image in a message about
    account security is the exact pattern people are told to distrust. The
    link is shown in full underneath the button, because a button whose target
    you cannot read is the other half of that pattern.
    """
    return (
        '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
        'font-size:15px;line-height:1.55;color:#0a0c10;max-width:520px">'
        f"<p>Hello {escape(who)},</p>"
        f"<p>{escape(lead)}</p>"
        f'<p style="margin:24px 0"><a href="{escape(link, quote=True)}" '
        'style="background:#084d77;color:#ffffff;text-decoration:none;'
        'padding:12px 20px;display:inline-block;font-weight:600">'
        f"{escape(action)}</a></p>"
        '<p style="font-size:13px;color:#5c6373">Or paste this into your browser:<br>'
        f'<span style="word-break:break-all">{escape(link)}</span></p>'
        f'<p style="font-size:13px;color:#5c6373">{escape(note)}</p>'
        '<p style="font-size:13px;color:#5c6373">Arus tracks mock IDX '
        "portfolios. No real money moves through it.</p>"
        "</div>"
    )


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
        html=_html(
            who,
            "Confirm this address to finish setting up your Arus account.",
            link,
            "Confirm address",
            "The link works once and expires in 24 hours. If you did not "
            "create an account, ignore this message — the address cannot be "
            "used until someone follows the link.",
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
        html=_html(
            who,
            "Someone asked to reset the password on this account.",
            link,
            "Set a new password",
            "The link works once and expires in one hour. Using it signs out "
            "every device currently on the account. If this was not you, no "
            "action is needed — the password is unchanged until someone "
            "follows the link.",
        ),
    )


#: Wire value -> what a person reading the subject line needs to see.
CONTACT_TOPICS = {
    "consulting": "Consulting",
    "research": "Market research",
    "platform": "Platform",
}


def contact_notification(
    name: str,
    email: str,
    message: str,
    topic: str = "platform",
    organisation: str | None = None,
) -> Message:
    """Tell the operator someone wrote in from the contact page.

    Text only, and that is a departure from the two messages above rather than
    an oversight. Those go to strangers, where a lone text/plain part carrying
    one bare URL is structurally what bulk phishing looks like. This one goes
    to the operator's own mailbox, where there is no filter to persuade and
    markup would only get between them and the message.

    The sender's address rides in Reply-To, not in From. Putting it in From
    would be a forgery of their domain, which is what SPF and DMARC exist to
    refuse — the message would land in spam or be rejected outright.
    """
    settings = get_settings()
    # Newlines in a header are how header injection works. Python's email
    # package raises on them, but a 500 is a poor way to discover that a name
    # contained a line break, so collapse whitespace before it gets near a
    # header rather than after.
    clean = " ".join(name.split())[:100] or "someone"
    org = " ".join((organisation or "").split())[:150]
    label = CONTACT_TOPICS.get(topic, "Enquiry")
    rule = "-" * 56
    return Message(
        to=settings.contact_inbox,
        # The topic leads the subject so the inbox sorts and filters itself.
        # A consulting enquiry and a bug report want different attention, and
        # the difference should be visible before the message is opened.
        subject=f"[{label}] Arus — {clean}" + (f" ({org})" if org else ""),
        reply_to=email,
        body=(
            f"""Topic: {label}
From: {clean}{f" — {org}" if org else ""}
Email: {email}
{rule}

{message}

{rule}
Left on the Arus contact page. Reply to this email and it goes straight
back to them. The message is also stored in `contact_messages`, so it
survives this email going astray."""
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
    # Gmail's relay backfills both, but a submission without them is a signal
    # in its own right: every real mail client sets them, and bulk senders
    # frequently do not. `make_msgid` takes its domain from the sender so the
    # id does not advertise the container's hostname.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.mail_sender.rpartition("@")[2])
    # A reply should reach a person, not this mailbox's automation.
    msg["Auto-Submitted"] = "auto-generated"
    if message.reply_to:
        msg["Reply-To"] = message.reply_to
    msg.set_content(message.body)
    # multipart/alternative. A single text/plain part carrying one bare URL is
    # structurally what bulk phishing looks like, and filters read structure
    # before they read content. The text part stays the canonical version.
    if message.html:
        msg.add_alternative(message.html, subtype="html")

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
