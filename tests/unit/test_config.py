# SPDX-License-Identifier: AGPL-3.0-or-later
"""Settings behaviour.

These cover the two config defects already found in this phase — a leaked
password and a blank env var that broke startup — so neither can come back.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from emeye.config import Settings

pytestmark = pytest.mark.unit

REQUIRED = {
    "EMEYE_POSTGRES_PASSWORD": "s3cret-value",
    "EMEYE_USER_AGENT": "emeye-test/0.0 (+mailto:test@example.invalid)",
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip any EMEYE_* the developer happens to have exported."""
    for key in list(os_environ_keys()):
        if key.startswith("EMEYE_"):
            monkeypatch.delenv(key, raising=False)


def os_environ_keys() -> list[str]:
    import os

    return list(os.environ)


def _make(monkeypatch: pytest.MonkeyPatch, **extra: str) -> Settings:
    for key, value in {**REQUIRED, **extra}.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make(monkeypatch, EMEYE_POSTGRES_DB="warehouse")
    assert settings.postgres_db == "warehouse"


def test_missing_required_value_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMEYE_USER_AGENT", REQUIRED["EMEYE_USER_AGENT"])
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "postgres_password" in str(exc.value)


def test_user_agent_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Honest identification is a collection obligation, not a default."""
    monkeypatch.setenv("EMEYE_POSTGRES_PASSWORD", "x")
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "user_agent" in str(exc.value)


@pytest.mark.parametrize(
    "flag",
    [
        "enable_beatport",
        "enable_musicbrainz",
        "enable_discogs",
        "enable_deezer",
        "enable_lastfm",
        "enable_listenbrainz",
        "enable_spotify",
    ],
)
def test_source_flags_default_off(monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    """Merging a collector must never start collection."""
    assert getattr(_make(monkeypatch), flag) is False


def test_password_absent_from_repr_and_dump(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: database_url was a computed_field and leaked into both."""
    settings = _make(monkeypatch)
    assert "s3cret-value" not in repr(settings)
    assert "s3cret-value" not in str(settings.model_dump())


def test_password_present_in_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make(monkeypatch)
    assert "s3cret-value" in settings.database_url
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_blank_optional_becomes_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: EMEYE_LOG_JSON= failed bool parsing and broke startup."""
    settings = _make(monkeypatch, EMEYE_LOG_JSON="", EMEYE_DISCOGS_TOKEN="")
    assert settings.log_json is None
    assert settings.discogs_token is None


def test_blank_token_is_not_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset token must not read as configured. SecretStr('') is truthy."""
    settings = _make(monkeypatch, EMEYE_LASTFM_API_KEY="")
    assert not settings.lastfm_api_key
