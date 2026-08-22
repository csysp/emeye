# SPDX-License-Identifier: AGPL-3.0-or-later
"""robots.txt policy — especially that it fails closed."""

from __future__ import annotations

import httpx
import pytest

from emeye.config import Settings
from emeye.http.robots import RobotsPolicy

pytestmark = pytest.mark.unit

ALLOW_ALL = "User-agent: *\nDisallow:\n"
DISALLOW_CHARTS = "User-agent: *\nDisallow: /charts/\n"
WITH_DELAY = "User-agent: *\nDisallow:\nCrawl-delay: 10\n"


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x",
        "user_agent": "emeye-test/0.0 (+mailto:t@example.invalid)",
    }
    return Settings(**{**base, **extra})  # type: ignore[arg-type]


def _policy(handler: object, **extra: object) -> RobotsPolicy:
    return RobotsPolicy(_settings(**extra), transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_allows_when_robots_permits() -> None:
    policy = _policy(lambda _request: httpx.Response(200, text=ALLOW_ALL))
    assert policy.is_allowed("https://example.invalid/charts/top100") is True


def test_denies_a_disallowed_path() -> None:
    policy = _policy(lambda _request: httpx.Response(200, text=DISALLOW_CHARTS))
    assert policy.is_allowed("https://example.invalid/charts/top100") is False
    assert policy.is_allowed("https://example.invalid/other") is True


def test_unreachable_robots_denies() -> None:
    """Fail closed. A network failure says nothing about what a host permits.

    This is the deliberate inversion of RobotFileParser's default, which treats
    unreachable as allow-everything.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    assert _policy(handler).is_allowed("https://example.invalid/anything") is False


def test_server_error_robots_denies() -> None:
    policy = _policy(lambda _request: httpx.Response(503))
    assert policy.is_allowed("https://example.invalid/anything") is False


def test_missing_robots_permits() -> None:
    """A 404 is a real answer: this host publishes no rules."""
    policy = _policy(lambda _request: httpx.Response(404))
    assert policy.is_allowed("https://example.invalid/anything") is True


def test_crawl_delay_is_reported() -> None:
    policy = _policy(lambda _request: httpx.Response(200, text=WITH_DELAY))
    assert policy.crawl_delay("https://example.invalid/x") == 10.0


def test_result_is_cached_per_host() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=ALLOW_ALL)

    policy = _policy(handler)
    for _ in range(3):
        policy.is_allowed("https://example.invalid/a")
    assert len(calls) == 1


def test_cache_expires_with_ttl() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=ALLOW_ALL)

    policy = _policy(handler, robots_cache_ttl_seconds=0)
    policy.is_allowed("https://example.invalid/a")
    policy.is_allowed("https://example.invalid/a")
    assert len(calls) == 2


def test_hosts_are_cached_independently() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200, text=ALLOW_ALL)

    policy = _policy(handler)
    policy.is_allowed("https://a.invalid/x")
    policy.is_allowed("https://b.invalid/x")
    assert set(seen) == {"a.invalid", "b.invalid"}
