# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migrations against a live PostgreSQL.

Skips rather than errors when no database is reachable, so the unit suite still
runs on a bare machine. A migration that only works forwards is a trap: the
first time a bad revision reaches the warehouse, `downgrade` is the way out.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from emeye.config import get_settings
from emeye.db.engine import check_connection, get_engine

pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module", autouse=True)
def _require_database() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    if not check_connection():
        pytest.skip("no PostgreSQL reachable — start it with `make up`", allow_module_level=True)


@pytest.fixture
def alembic_config():  # type: ignore[no-untyped-def]
    from alembic.config import Config

    config = Config("alembic.ini")
    return config


def _tables() -> set[str]:
    return set(inspect(get_engine()).get_table_names())


def test_upgrade_creates_schema_meta(alembic_config) -> None:  # type: ignore[no-untyped-def]
    from alembic import command

    command.upgrade(alembic_config, "head")
    assert "schema_meta" in _tables()
    assert "alembic_version" in _tables()


def test_schema_meta_is_seeded() -> None:
    with get_engine().connect() as conn:
        value = conn.execute(
            text("select value from schema_meta where key = 'schema_initialized_at'")
        ).scalar_one_or_none()
    assert value is not None


def test_downgrade_then_upgrade_round_trips(alembic_config) -> None:  # type: ignore[no-untyped-def]
    from alembic import command

    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    assert "schema_meta" not in _tables()

    command.upgrade(alembic_config, "head")
    assert "schema_meta" in _tables()


def test_upgrade_is_idempotent(alembic_config) -> None:  # type: ignore[no-untyped-def]
    """Re-running a completed migration must be a no-op, not an error."""
    from alembic import command

    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")
    assert "schema_meta" in _tables()


def test_models_match_migrations(alembic_config) -> None:  # type: ignore[no-untyped-def]
    """Autogenerate must see no pending diff, or models and schema have drifted."""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from emeye.db import models  # noqa: F401
    from emeye.db.base import Base

    command.upgrade(alembic_config, "head")
    with get_engine().connect() as conn:
        context = MigrationContext.configure(conn)
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"models and migrations disagree: {diff}"
