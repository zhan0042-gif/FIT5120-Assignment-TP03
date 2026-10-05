"""A small in-process rate limit for typed safety questions.

Every typed question spends a shared hosted quota (the rendezvous explanation draws
on the same one) and the endpoint needs no login. Household ids are free to mint, so
the per-household limit only stops one browser looping; the overall limit is the
real protection. The counters live in this process, so with several workers each
would count separately and the limits would apply per worker.
"""

import threading
import time
from collections import deque
from collections.abc import Callable


class AskRateLimit:
    """Allow at most `per_household` questions per household and `overall` in total
    in any `window_seconds`. A refused request uses up nothing."""

    def __init__(
        self,
        per_household: int = 6,
        overall: int = 30,
        window_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sweep_above: int = 5000,
    ) -> None:
        self.per_household = per_household
        self.overall = overall
        self.window_seconds = window_seconds
        self.clock = clock
        self.sweep_above = sweep_above
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, household_id: str) -> bool:
        now = self.clock()
        household_key = f"household:{household_id}"
        with self._lock:
            if (
                self._count(household_key, now) >= self.per_household
                or self._count("overall", now) >= self.overall
            ):
                return False
            self._events.setdefault(household_key, deque()).append(now)
            self._events.setdefault("overall", deque()).append(now)
            if len(self._events) > self.sweep_above:
                self._sweep(now)
            return True

    def _count(self, key: str, now: float) -> int:
        events = self._events.get(key)
        if not events:
            return 0
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._events[key]
            return 0
        return len(events)

    def _sweep(self, now: float) -> None:
        for key in list(self._events):
            self._count(key, now)
