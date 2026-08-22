# SPDX-License-Identifier: AGPL-3.0-or-later
"""Per-host rate limiting."""

from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

from emeye.config import Settings
from emeye.logging import get_logger

log = get_logger(__name__)


class RateLimiter:
    """Enforces a minimum interval between requests to the same host.

    Hosts are independent: waiting on MusicBrainz must not delay Deezer.
    """

    def __init__(self, settings: Settings) -> None:
        self._default_interval = 1.0 / max(settings.default_rate_limit_per_sec, 0.001)
        self._overrides = {
            host: 1.0 / max(rate, 0.001) for host, rate in settings.per_host_rate_limits.items()
        }
        self._jitter = max(settings.rate_limit_jitter_seconds, 0.0)
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._registry_lock = threading.Lock()

    def _interval_for(self, host: str, crawl_delay: float | None) -> float:
        interval = self._overrides.get(host, self._default_interval)
        if crawl_delay is not None:
            # Take the stricter of our configured rate and the host's own
            # declared delay. The host's request is a floor, not a ceiling.
            interval = max(interval, crawl_delay)
        return interval

    def _lock_for(self, host: str) -> threading.Lock:
        with self._registry_lock:
            return self._locks[host]

    def wait(self, url: str, crawl_delay: float | None = None) -> float:
        """Block until it is polite to request ``url``. Returns seconds slept."""
        host = urlparse(url).netloc
        interval = self._interval_for(host, crawl_delay)

        with self._lock_for(host):
            elapsed = time.monotonic() - self._last_request[host]
            # Jitter matters: a perfectly periodic request pattern is both more
            # detectable and less considerate than a slightly irregular one.
            delay = max(0.0, interval - elapsed) + random.uniform(0, self._jitter)  # noqa: S311
            if delay > 0:
                time.sleep(delay)
            self._last_request[host] = time.monotonic()

        if delay > 0:
            log.debug("rate_limited", host=host, slept_seconds=round(delay, 3))
        return delay
