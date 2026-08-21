# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine and session behaviour, without a database."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMEYE_POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("EMEYE_USER_AGENT", "emeye-test/0.0 (+mailto:t@example.invalid)")
    monkeypatch.setenv("EMEYE_POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("EMEYE_POSTGRES_PORT", "59999")


def test_import_does_not_connect() -> None:
    """Importing must not need a database: --help and unit tests depend on it."""
    import importlib

    module = importlib.import_module("emeye.db.engine")
    assert module is not None


def test_engine_is_built_lazily_and_cached() -> None:
    from emeye.config import get_settings
    from emeye.db.engine import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    assert get_engine() is get_engine()


def test_check_connection_returns_false_rather_than_raising() -> None:
    from emeye.config import get_settings
    from emeye.db.engine import check_connection, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    assert check_connection() is False


def test_check_connection_does_not_leak_the_password(capsys: pytest.CaptureFixture[str]) -> None:
    """The failure path logs the driver error; it must not carry credentials."""
    import emeye.config as config_module
    import emeye.db.engine as engine_module

    config_module.get_settings.cache_clear()
    engine_module.get_engine.cache_clear()
    engine_module.check_connection()
    captured = capsys.readouterr()
    assert "x@127.0.0.1" not in captured.out + captured.err


def test_session_scope_rolls_back_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import emeye.db.engine as engine_module

    events: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(engine_module, "_session_factory", lambda: FakeSession)

    with pytest.raises(ValueError, match="boom"), engine_module.session_scope():
        raise ValueError("boom")

    assert events == ["rollback", "close"]


def test_session_scope_commits_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import emeye.db.engine as engine_module

    events: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:  # pragma: no cover - not reached
            events.append("rollback")

        def close(self) -> None:
            events.append("close")

    monkeypatch.setattr(engine_module, "_session_factory", lambda: FakeSession)

    with engine_module.session_scope():
        pass

    assert events == ["commit", "close"]


def test_sqlalchemy_error_is_importable() -> None:
    assert issubclass(SQLAlchemyError, Exception)
