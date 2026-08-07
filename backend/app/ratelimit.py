"""A deliberately small in-process rate limiter.

In-process and per-worker, which is right here and would be wrong almost
anywhere else: this app runs a SINGLE uvicorn worker on purpose, because
APScheduler runs in-process and a second worker would mean two schedulers
racing (see docker-compose.prod.yml). One process means one counter and no
second one to disagree with it. Redis would be a dependency bought to solve a
problem this deployment does not have.

It exists for POST /auth/demo, which writes rows without authentication.
"""

import time
from collections import deque

from fastapi import Request

# Above this many tracked keys, sweep the ones whose window has fully expired.
# Without it an attacker rotating source addresses grows the dict without
# bound — the limiter itself becoming the memory leak it was added to prevent.
_PRUNE_THRESHOLD = 1024


class SlidingWindowLimiter:
    """Allow `limit` events per `window` seconds, per key.

    Sliding rather than fixed-window: a fixed window lets a caller spend the
    whole allowance at 11:59:59 and the whole next one at 12:00:00, which is
    twice the intended rate at exactly the moment a burst matters.
    """

    def __init__(self, limit: int, window: float) -> None:
        self._limit = limit
        self._window = window
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record an event for `key` and report whether it is within budget."""
        # Monotonic, not wall-clock: an NTP correction stepping the clock
        # backwards would otherwise strand entries in the future and lock a
        # caller out until real time caught up.
        now = time.monotonic() if now is None else now
        cutoff = now - self._window

        hits = self._hits.get(key)
        if hits is None:
            hits = self._hits[key] = deque()
            if len(self._hits) > _PRUNE_THRESHOLD:
                self._prune(cutoff)

        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self._limit:
            return False

        hits.append(now)
        return True

    def _prune(self, cutoff: float) -> None:
        for key in [k for k, d in self._hits.items() if not d or d[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        """Drop all state. For tests — nothing in the app calls this."""
        self._hits.clear()


def client_key(request: Request) -> str:
    """Best-effort caller identity for rate limiting.

    Behind Caddy the socket peer is always the proxy, so X-Forwarded-For is
    the only source of the caller's address.

    Take the LAST entry, not the first. Caddy APPENDS the peer it actually
    saw, so anything the client puts in the header itself lands to the LEFT of
    the truth. Reading the leftmost value — the usual reflex, and what most
    snippets do — would let any caller mint a fresh rate-limit bucket per
    request by sending a header, which is worse than having no limiter at all
    because it looks like one.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"
