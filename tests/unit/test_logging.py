# SPDX-License-Identifier: AGPL-3.0-or-later
"""Logging configuration."""

from __future__ import annotations

import json

import pytest

from emeye.config import Settings
from emeye.logging import configure_logging, get_logger, reset_logging

pytestmark = pytest.mark.unit


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x",
        "user_agent": "emeye-test/0.0 (+mailto:t@example.invalid)",
    }
    return Settings(**{**base, **extra})  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_logging()


def test_json_output_is_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_settings(log_json=True))
    get_logger("test").info("chart_fetched", chart="top100", items=100)
    line = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "chart_fetched"
    assert payload["chart"] == "top100"
    assert payload["items"] == 100


def test_service_is_bound(capsys: pytest.CaptureFixture[str]) -> None:
    """The scheduler, app and UI share a log stream and must be tellable apart."""
    configure_logging(_settings(log_json=True, service_name="scheduler"))
    get_logger("test").info("tick")
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["service"] == "scheduler"


def test_configure_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    """Called from the CLI callback and test fixtures; must not double-render."""
    settings = _settings(log_json=True)
    configure_logging(settings)
    configure_logging(settings)
    get_logger("test").info("once")
    lines = [ln for ln in capsys.readouterr().err.strip().splitlines() if "once" in ln]
    assert len(lines) == 1


def test_timestamp_is_timezone_aware(capsys: pytest.CaptureFixture[str]) -> None:
    """Naive timestamps in a time-series project are a silent correctness bug."""
    configure_logging(_settings(log_json=True))
    get_logger("test").info("event")
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["timestamp"].endswith("Z")
