"""The rate limiter guarding POST /auth/demo.

Pure and synchronous — the limiter takes an injected clock precisely so these
never sleep. Kept out of test_demo.py because that module marks everything in
it as asyncio.
"""

from app.ratelimit import SlidingWindowLimiter, client_key


def test_budget_is_spent_and_then_refilled_as_events_age_out():
    limiter = SlidingWindowLimiter(limit=2, window=60)
    assert limiter.allow("a", now=0.0)
    assert limiter.allow("a", now=1.0)
    assert not limiter.allow("a", now=2.0)  # budget spent

    # Sliding, not fixed: the t=0 event ages out exactly at t=60 and frees one
    # slot. The t=1 event has not, so the budget is 1 here, not a fresh 2 —
    # which is the whole reason for a sliding window. A fixed window would
    # hand back the full allowance at the boundary and permit double the
    # intended rate across it.
    assert limiter.allow("a", now=60.0)
    assert not limiter.allow("a", now=60.5)

    # Both original events gone by t=61.5.
    assert limiter.allow("a", now=61.5)


def test_buckets_are_per_key():
    limiter = SlidingWindowLimiter(limit=1, window=60)
    assert limiter.allow("a", now=0.0)
    assert not limiter.allow("a", now=1.0)
    assert limiter.allow("b", now=1.0)


def test_reset_clears_every_bucket():
    limiter = SlidingWindowLimiter(limit=1, window=60)
    assert limiter.allow("a", now=0.0)
    assert not limiter.allow("a", now=1.0)
    limiter.reset()
    assert limiter.allow("a", now=2.0)


class _FakeRequest:
    def __init__(self, headers: dict[str, str], peer: str | None = "10.0.0.5"):
        self.headers = headers

        class _Client:
            host = peer

        self.client = _Client() if peer else None


def test_client_key_trusts_the_rightmost_forwarded_hop():
    """A client-supplied X-Forwarded-For must not buy a fresh bucket.

    Caddy APPENDS the peer it actually saw, so the trustworthy value is last
    and anything the caller invented sits to its left. Reading the leftmost
    entry — the usual reflex, and what most snippets do — would let anyone
    rotate their own rate-limit identity by sending one header, leaving a
    limiter that looks present and enforces nothing.
    """
    spoofed = _FakeRequest({"x-forwarded-for": "1.2.3.4, 203.0.113.9"})
    assert client_key(spoofed) == "203.0.113.9"


def test_client_key_handles_a_single_hop_and_stray_whitespace():
    assert client_key(_FakeRequest({"x-forwarded-for": " 203.0.113.9 "})) == "203.0.113.9"


def test_client_key_falls_back_to_the_socket_peer():
    """No proxy in front (local dev, or a direct hit) — use the real peer."""
    assert client_key(_FakeRequest({})) == "10.0.0.5"
    assert client_key(_FakeRequest({}, peer=None)) == "unknown"
