# SPDX-License-Identifier: AGPL-3.0-or-later
"""Per-host rate limiting."""

from __future__ import annotations

import pytest

from emeye.config import Settings
from emeye.http.limiter import RateLimiter

pytestmark = pytest.mark.unit


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x",
        "user_agent": "emeye-test/0.0 (+mailto:t@example.invalid)",
        "rate_limit_jitter_seconds": 0.0,
    }
    return Settings(**{**base, **extra})  # type: ignore[arg-type]


def test_first_request_does_not_wait() -> None:
    limiter = RateLimiter(_settings(default_rate_limit_per_sec=1.0))
    assert limiter.wait("https://example.invalid/a") == pytest.approx(0.0, abs=0.05)


def test_second_request_to_same_host_waits() -> None:
    limiter = RateLimiter(_settings(default_rate_limit_per_sec=20.0))
    limiter.wait("https://example.invalid/a")
    slept = limiter.wait("https://example.invalid/b")
    assert slept > 0


def test_different_hosts_do_not_block_each_other() -> None:
    limiter = RateLimiter(_settings(default_rate_limit_per_sec=20.0))
    limiter.wait("https://a.invalid/x")
    assert limiter.wait("https://b.invalid/x") == pytest.approx(0.0, abs=0.05)


def test_per_host_override_is_applied() -> None:
    limiter = RateLimiter(
        _settings(default_rate_limit_per_sec=100.0, per_host_rate_limits={"slow.invalid": 20.0})
    )
    limiter.wait("https://slow.invalid/x")
    slow = limiter.wait("https://slow.invalid/y")
    limiter.wait("https://fast.invalid/x")
    fast = limiter.wait("https://fast.invalid/y")
    assert slow > fast


def test_crawl_delay_wins_when_stricter() -> None:
    """A host's declared delay is a floor, not a ceiling."""
    limiter = RateLimiter(_settings(default_rate_limit_per_sec=1000.0))
    limiter.wait("https://example.invalid/a", crawl_delay=0.2)
    assert limiter.wait("https://example.invalid/b", crawl_delay=0.2) > 0.1


def test_jitter_is_bounded() -> None:
    limiter = RateLimiter(
        _settings(default_rate_limit_per_sec=1000.0, rate_limit_jitter_seconds=0.1)
    )
    for _ in range(5):
        assert limiter.wait("https://example.invalid/x") <= 0.2
