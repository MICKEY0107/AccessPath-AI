"""Process-wide request pacing for external planner providers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ProcessWideCallPacer:
    """Serialize provider request starts across independently created clients.

    Each evaluation run creates its own client. This gate keeps the configured
    minimum interval intact when one run finishes and the next one begins in
    the same worker process.
    """

    _locks: dict[str, threading.Lock] = {}
    _last_call_started: dict[str, float] = {}
    _registry_lock = threading.Lock()

    @classmethod
    def wait_for_turn(
        cls,
        *,
        provider: str,
        min_interval_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Wait until this process may start its next request for ``provider``."""
        with cls._registry_lock:
            provider_lock = cls._locks.setdefault(provider, threading.Lock())

        with provider_lock:
            now = monotonic()
            previous_start = cls._last_call_started.get(provider)
            if previous_start is not None:
                remaining = max(0.0, min_interval_seconds - (now - previous_start))
                if remaining:
                    sleep(remaining)
            cls._last_call_started[provider] = monotonic()
