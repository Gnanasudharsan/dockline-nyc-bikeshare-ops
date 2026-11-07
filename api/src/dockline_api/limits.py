"""In-memory rate limits for /ask (one API process; enough for a single VM)."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limit per client plus a fixed daily cap for everyone.

    The daily cap protects the free LLM quota; the per-client window keeps one visitor
    from using all of it.
    """

    def __init__(self, per_minute: int, per_day: int) -> None:
        """Set both limits."""
        self.per_minute = per_minute
        self.per_day = per_day
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._day = time.strftime("%Y-%m-%d")
        self._day_count = 0

    def check(self, client: str, now: float | None = None) -> str | None:
        """Record a request; return a reason string when it must be rejected."""
        now = time.monotonic() if now is None else now
        today = time.strftime("%Y-%m-%d")
        if today != self._day:
            self._day, self._day_count = today, 0
        if self._day_count >= self.per_day:
            return "Ask the Data has reached today's question limit. Try again tomorrow."
        window = self._hits[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            wait = int(60 - (now - window[0])) + 1
            return f"Too many questions. Wait {wait} seconds and try again."
        window.append(now)
        self._day_count += 1
        return None
