# SPDX-License-Identifier: AGPL-3.0-or-later
"""Engine and session factory.

The engine is built lazily and cached. Constructing one at import time would
make ``emeye --help`` and every unit test depend on a reachable database.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from emeye.config import Settings, get_settings
from emeye.logging import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine, building it on first use."""
    settings: Settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any exception."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_connection() -> bool:
    """Return whether the warehouse is reachable.

    Returns False rather than raising: callers are health checks and status
    output, for which an unreachable database is an answer, not a crash.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001 - deliberately broad; reported, not swallowed
        log.warning("database_unreachable", error=str(exc))
        return False
    return True
