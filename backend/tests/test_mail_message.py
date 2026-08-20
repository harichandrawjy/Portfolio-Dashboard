"""Message construction — pure, so no client, no database, no event loop.

Both messages went to spam on first contact with a real inbox. Authentication
was not the cause: sending through Gmail means Google signs as d=gmail.com and
SPF passes via _spf.google.com, and gmail.com's DMARC is p=none. What was left
was the message's own shape and the domain its link points at. Shape is
fixable here; the link domain is not, and is the larger of the two.
"""

import re

from app import mail


def _token_in(text: str) -> str:
    m = re.search(r"token=([\w\-]+)", text)
    assert m, f"no link found in:\n{text[:400]}"
    return m.group(1)


def test_both_halves_carry_the_same_link():
    """The link now exists twice per message, once per MIME part. Someone
    clicking the button and someone pasting the text must land in the same
    place, and nothing else would catch the two drifting apart."""
    for build in (mail.verification_message, mail.reset_message):
        m = build("someone@example.com", "TOK-EN_123", "Hari")
        assert m.html, "without an html half it is not multipart/alternative"
        assert _token_in(m.html) == _token_in(m.body) == "TOK-EN_123"


def test_the_html_half_escapes_the_display_name():
    """The name is user-supplied and lands in markup."""
    m = mail.verification_message(
        "someone@example.com", "TOK", "<script>alert(1)</script>"
    )
    assert "<script>" not in m.html
    assert "&lt;script&gt;" in m.html


def test_the_html_half_pulls_in_nothing_remote():
    """No images, no stylesheets, no tracking pixel. Each is a spam signal on
    its own, and a remote image in a message about account security is the
    exact pattern people are told to distrust. The only URL in the markup
    should be the link the recipient is being asked to follow."""
    m = mail.reset_message("someone@example.com", "TOK", None)
    lowered = m.html.lower()
    assert "<img" not in lowered
    assert "<link" not in lowered
    assert "<style" not in lowered
    assert "url(" not in lowered

    urls = re.findall(r"https?://[^\s\"'<>]+", m.html)
    assert urls, "the message should contain its own link"
    assert all("/reset?token=" in u for u in urls), urls


def test_a_missing_display_name_falls_back_to_the_address():
    m = mail.verification_message("someone@example.com", "TOK", None)
    assert "someone@example.com" in m.body
    assert "someone@example.com" in m.html
