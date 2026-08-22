# SPDX-License-Identifier: AGPL-3.0-or-later
"""robots.txt, treated as a first-class component rather than a checkbox.

The important deviation from the standard library: this **fails closed**.
``urllib.robotparser.RobotFileParser`` treats an unreachable robots.txt as
allow-everything, which is precisely backwards for a project whose collection
posture is binding. A host that will not tell us its rules does not get
crawled.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from emeye.config import Settings
from emeye.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class _CacheEntry:
    parser: RobotFileParser | None
    crawl_delay: float | None
    fetched_at: float
    reachable: bool


class RobotsPolicy:
    """Per-host robots.txt cache with a TTL.

    robots.txt is fetched with a plain short-timeout client rather than through
    ``PoliteClient``: routing it through the rate-limited client would make the
    two mutually recursive, since the client consults this policy on every
    request.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._ttl = float(settings.robots_cache_ttl_seconds)
        self._cache: dict[str, _CacheEntry] = {}
        self._transport = transport

    def _fetch(self, origin: str) -> _CacheEntry:
        url = f"{origin}/robots.txt"
        try:
            with httpx.Client(
                timeout=10.0,
                headers={"User-Agent": self._settings.user_agent},
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
        except httpx.HTTPError as exc:
            # Unreachable is NOT permission. A network failure tells us nothing
            # about what the host permits, so we decline to guess.
            log.warning("robots_unreachable", origin=origin, error=str(exc))
            return _CacheEntry(None, None, time.monotonic(), reachable=False)

        if response.status_code == 404:
            # A 404 is a real answer: this host publishes no rules.
            parser = RobotFileParser()
            parser.parse([])
            return _CacheEntry(parser, None, time.monotonic(), reachable=True)

        if response.status_code >= 400:
            log.warning("robots_error_status", origin=origin, status=response.status_code)
            return _CacheEntry(None, None, time.monotonic(), reachable=False)

        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        delay = parser.crawl_delay(self._settings.user_agent)
        return _CacheEntry(
            parser,
            float(delay) if delay is not None else None,
            time.monotonic(),
            reachable=True,
        )

    def _entry(self, origin: str) -> _CacheEntry:
        cached = self._cache.get(origin)
        if cached is not None and (time.monotonic() - cached.fetched_at) < self._ttl:
            return cached
        entry = self._fetch(origin)
        self._cache[origin] = entry
        return entry

    def is_allowed(self, url: str) -> bool:
        """Whether the configured User-Agent may fetch ``url``."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        entry = self._entry(origin)

        if not entry.reachable or entry.parser is None:
            log.warning("robots_denied_unreachable", url=url)
            return False

        allowed = entry.parser.can_fetch(self._settings.user_agent, url)
        if not allowed:
            # A silent denial is indistinguishable from a broken collector.
            log.warning("robots_denied", url=url)
        else:
            log.debug("robots_allowed", url=url)
        return allowed

    def crawl_delay(self, url: str) -> float | None:
        """Host-declared Crawl-delay, if any."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return self._entry(origin).crawl_delay
