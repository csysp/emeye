# SPDX-License-Identifier: AGPL-3.0-or-later
"""The polite client's guarantees.

Every one of these is a promise CLAUDE.md makes about how emeye behaves toward
upstream services. They are tested rather than asserted in a docstring.

All HTTP is mocked. The Phase 1 network guard already makes a real call
impossible; these pass because they are correct, not because the guard caught
them.
"""

from __future__ import annotations

import httpx
import pytest

from emeye.config import Settings
from emeye.http.client import (
    FetchResult,
    PoliteClient,
    RetryExhausted,
    RobotsDenied,
    SourceDisabled,
)

pytestmark = pytest.mark.unit

ALLOW_ALL = "User-agent: *\nDisallow:\n"
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x",
        "user_agent": "emeye-test/0.0 (+mailto:t@example.invalid)",
        "enable_deezer": True,
        "rate_limit_jitter_seconds": 0.0,
        "default_rate_limit_per_sec": 1000.0,
        "max_retries": 3,
    }
    return Settings(**{**base, **extra})  # type: ignore[arg-type]


class Recorder:
    """Mock transport recording every request it serves."""

    def __init__(self, robots: str = ALLOW_ALL, responses: list[httpx.Response] | None = None):
        self.robots = robots
        self.responses = responses or [httpx.Response(200, json={"ok": True})]
        self.requests: list[httpx.Request] = []
        self._index = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=self.robots)
        self.requests.append(request)
        response = self.responses[min(self._index, len(self.responses) - 1)]
        self._index += 1
        return response


def _client(recorder: Recorder, sleeps: list[float] | None = None, **extra: object) -> PoliteClient:
    return PoliteClient(
        "deezer",
        settings=_settings(**extra),
        transport=httpx.MockTransport(recorder),
        sleep=(sleeps.append if sleeps is not None else (lambda _: None)),
    )


def test_disabled_source_cannot_be_constructed() -> None:
    with pytest.raises(SourceDisabled, match="deezer"):
        PoliteClient("deezer", settings=_settings(enable_deezer=False))


def test_disabled_source_issues_no_request() -> None:
    """Not merely 'raises' — no request must reach the wire at all."""
    recorder = Recorder()
    with pytest.raises(SourceDisabled):
        PoliteClient(
            "deezer",
            settings=_settings(enable_deezer=False),
            transport=httpx.MockTransport(recorder),
        )
    assert recorder.requests == []


def test_robots_denial_raises_and_issues_no_request() -> None:
    recorder = Recorder(robots=DISALLOW_ALL)
    with _client(recorder) as client, pytest.raises(RobotsDenied):
        client.get("https://example.invalid/charts")
    assert recorder.requests == []


def test_unreachable_robots_blocks_the_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("no robots", request=request)
        raise AssertionError("request must not be issued when robots is unreachable")

    client = PoliteClient(
        "deezer", settings=_settings(), transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    with client, pytest.raises(RobotsDenied):
        client.get("https://example.invalid/anything")


def test_successful_fetch_returns_result() -> None:
    recorder = Recorder(responses=[httpx.Response(200, json={"tracks": [1, 2]})])
    with _client(recorder) as client:
        result = client.get("https://example.invalid/charts")
    assert isinstance(result, FetchResult)
    assert result.status_code == 200
    assert b"tracks" in result.body


def test_configured_user_agent_is_sent() -> None:
    """Identify honestly. Never impersonate a browser."""
    recorder = Recorder()
    with _client(recorder) as client:
        client.get("https://example.invalid/x")
    assert recorder.requests[0].headers["User-Agent"] == (
        "emeye-test/0.0 (+mailto:t@example.invalid)"
    )


def test_404_is_not_retried() -> None:
    """4xx other than 429 means we asked wrongly; repeating it is pointless."""
    recorder = Recorder(responses=[httpx.Response(404)])
    with _client(recorder) as client:
        result = client.get("https://example.invalid/missing")
    assert result.status_code == 404
    assert len(recorder.requests) == 1


def test_503_is_retried_then_gives_up() -> None:
    recorder = Recorder(responses=[httpx.Response(503)])
    with _client(recorder) as client, pytest.raises(RetryExhausted):
        client.get("https://example.invalid/flaky")
    assert len(recorder.requests) == 3


def test_transient_failure_then_success() -> None:
    recorder = Recorder(responses=[httpx.Response(503), httpx.Response(200, json={"ok": 1})])
    with _client(recorder) as client:
        result = client.get("https://example.invalid/x")
    assert result.status_code == 200


def test_retry_after_is_honoured_exactly() -> None:
    """A 429 is the upstream telling us we got it wrong."""
    sleeps: list[float] = []
    recorder = Recorder(
        responses=[httpx.Response(429, headers={"Retry-After": "37"}), httpx.Response(200)]
    )
    with _client(recorder, sleeps=sleeps) as client:
        client.get("https://example.invalid/limited")
    assert 37.0 in sleeps


def test_retry_after_longer_than_timeout_is_still_honoured() -> None:
    """Substituting our own shorter backoff is exactly what the posture forbids."""
    sleeps: list[float] = []
    recorder = Recorder(
        responses=[httpx.Response(429, headers={"Retry-After": "300"}), httpx.Response(200)]
    )
    with _client(recorder, sleeps=sleeps, http_timeout_seconds=30.0) as client:
        client.get("https://example.invalid/limited")
    assert max(sleeps) == 300.0


def test_missing_retry_after_falls_back_to_backoff() -> None:
    sleeps: list[float] = []
    recorder = Recorder(responses=[httpx.Response(429), httpx.Response(200)])
    with _client(recorder, sleeps=sleeps) as client:
        client.get("https://example.invalid/limited")
    assert sleeps and all(s > 0 for s in sleeps)


def test_http_date_retry_after_does_not_crash() -> None:
    """An HTTP-date Retry-After falls back rather than mis-parsing a clock."""
    sleeps: list[float] = []
    recorder = Recorder(
        responses=[
            httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
            httpx.Response(200),
        ]
    )
    with _client(recorder, sleeps=sleeps) as client:
        result = client.get("https://example.invalid/limited")
    assert result.status_code == 200


def test_connection_errors_are_retried_then_raise() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL)
        attempts["n"] += 1
        raise httpx.ConnectError("boom", request=request)

    client = PoliteClient(
        "deezer", settings=_settings(), transport=httpx.MockTransport(handler), sleep=lambda _: None
    )
    with client, pytest.raises(RetryExhausted):
        client.get("https://example.invalid/x")
    assert attempts["n"] == 3
