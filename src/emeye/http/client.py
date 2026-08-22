# SPDX-License-Identifier: AGPL-3.0-or-later
"""The polite client. All outbound HTTP goes through here."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from emeye.config import Settings, get_settings
from emeye.http.limiter import RateLimiter
from emeye.http.robots import RobotsPolicy
from emeye.logging import get_logger

log = get_logger(__name__)

# Status codes worth another attempt. 4xx other than 429 means we asked wrongly;
# retrying an incorrect request is just repeating it.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class SourceDisabled(RuntimeError):
    """Raised when a client is built for a source that is switched off."""


class RobotsDenied(RuntimeError):
    """Raised when robots.txt forbids a URL. Never a silent skip."""


class RetryExhausted(RuntimeError):
    """Raised when every attempt failed."""


@dataclass(frozen=True)
class FetchResult:
    """One completed response, shaped for ``bronze.store``."""

    url: str
    status_code: int
    body: bytes
    headers: dict[str, str]
    elapsed_ms: int
    content_type: str | None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class PoliteClient:
    """Rate-limited, robots-respecting, honestly-identified HTTP client.

    Constructed *for a source*, and refuses to exist if that source is
    disabled. Gating lives here rather than in the caller so that a collector
    cannot start collecting merely because someone called it.
    """

    def __init__(
        self,
        source: str,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self._settings = settings or get_settings()
        self._source = source

        flag = f"enable_{source}"
        if not getattr(self._settings, flag, False):
            raise SourceDisabled(
                f"source '{source}' is disabled. Set EMEYE_{flag.upper()}=true to enable it "
                f"— collection is a deliberate act, never a side effect of running code."
            )

        self._robots = RobotsPolicy(self._settings, transport=transport)
        self._limiter = RateLimiter(self._settings)
        self._sleep = sleep
        self._client = httpx.Client(
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": self._settings.user_agent},
            transport=transport,
            follow_redirects=True,
        )

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            # HTTP-date form. Rather than parse it and risk a clock-skew
            # miscalculation, fall back to the caller's backoff.
            return None

    def get(self, url: str, params: dict[str, Any] | None = None) -> FetchResult:
        """Fetch a URL politely, or raise explaining why we did not."""
        if not self._robots.is_allowed(url):
            raise RobotsDenied(f"robots.txt disallows {url} for {self._settings.user_agent}")

        crawl_delay = self._robots.crawl_delay(url)
        attempts = max(1, self._settings.max_retries)
        backoff = 1.0
        last_status: int | None = None

        for attempt in range(1, attempts + 1):
            self._limiter.wait(url, crawl_delay=crawl_delay)
            started = time.monotonic()

            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt == attempts:
                    raise RetryExhausted(f"{url}: {exc}") from exc
                log.warning(
                    "http_error_retrying",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                    source=self._source,
                )
                self._sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue

            elapsed_ms = int((time.monotonic() - started) * 1000)
            last_status = response.status_code

            if response.status_code not in RETRYABLE_STATUS:
                log.info(
                    "http_fetched",
                    url=url,
                    status=response.status_code,
                    elapsed_ms=elapsed_ms,
                    bytes=len(response.content),
                    source=self._source,
                )
                return FetchResult(
                    url=str(response.url),
                    status_code=response.status_code,
                    body=response.content,
                    headers=dict(response.headers),
                    elapsed_ms=elapsed_ms,
                    content_type=response.headers.get("Content-Type"),
                )

            if attempt == attempts:
                break

            # Retry-After is obeyed absolutely, including values longer than our
            # own timeout. A 429 is the upstream telling us we got it wrong;
            # substituting a shorter backoff of our own is exactly the behaviour
            # the collection posture forbids.
            retry_after = self._retry_after_seconds(response)
            delay = retry_after if retry_after is not None else backoff
            log.warning(
                "http_retrying",
                url=url,
                status=response.status_code,
                attempt=attempt,
                sleep_seconds=delay,
                honoured_retry_after=retry_after is not None,
                source=self._source,
            )
            self._sleep(delay)
            if retry_after is None:
                backoff = min(backoff * 2, 60.0)

        raise RetryExhausted(f"{url}: gave up after {attempts} attempts, last status {last_status}")
