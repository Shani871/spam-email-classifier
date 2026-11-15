"""In-process sliding-window rate limits.

Limits are held in memory per app process. They protect a single-instance deployment
from scripted abuse (bulk checks, password guessing against third-party mailboxes
through the IMAP connector). They reset on restart and are not shared across replicas.
"""
from collections import defaultdict, deque
import threading
import time

# action -> (max events, window in seconds)
LIMITS = {
    "check": (30, 60),
    "batch_check": (3, 300),
    "inbox_scan": (10, 60),
    "inbox_connect": (5, 300),
    # Keyed by the target mailbox, not the caller: caps guesses against one account.
    "inbox_connect_target": (8, 900),
}


class RateLimitExceeded(ValueError):
    """Raised when a caller exceeds a limit. Subclasses ValueError so page-level
    handlers that already report ValueError show the message instead of a traceback."""

    def __init__(self, action, retry_after):
        self.action = action
        self.retry_after = max(1, int(retry_after + 0.999))
        super().__init__(f"Too many requests. Try again in {self.retry_after} seconds.")


class RateLimiter:
    def __init__(self, limits=None, clock=time.monotonic):
        self._limits = dict(limits or LIMITS)
        self._clock = clock
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, action, key):
        """Record one event; raise RateLimitExceeded when the window is full."""
        limit, window = self._limits[action]
        now = self._clock()
        with self._lock:
            events = self._events[(action, str(key))]
            while events and now - events[0] >= window:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitExceeded(action, window - (now - events[0]))
            events.append(now)
            if len(self._events) > 50_000:
                self._prune(now)

    def _prune(self, now):
        for name in [n for n, ev in self._events.items() if not ev or now - ev[-1] >= self._limits[n[0]][1]]:
            del self._events[name]

    def reset(self):
        with self._lock:
            self._events.clear()


limiter = RateLimiter()


def client_key(identity=""):
    """Best available caller key: client IP when known, else the session identity.

    X-Forwarded-For is only trusted when SPAMGUARD_TRUST_PROXY=1, i.e. when the app
    is reachable solely through a reverse proxy that sets the header.
    """
    import os
    try:
        import streamlit as st
        if os.environ.get("SPAMGUARD_TRUST_PROXY") == "1":
            forwarded = st.context.headers.get("X-Forwarded-For", "")
            if forwarded:
                return "ip:" + forwarded.split(",")[0].strip()
        address = st.context.ip_address
        if address:
            return "ip:" + address
    except Exception:
        pass
    return "id:" + str(identity or "anonymous")


def enforce(action, identity=""):
    limiter.hit(action, client_key(identity))
