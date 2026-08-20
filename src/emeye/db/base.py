# SPDX-License-Identifier: AGPL-3.0-or-later
"""Declarative base.

Every model must be imported into :mod:`emeye.db.models` so that Alembic's
autogenerate sees it. A model that is defined but never imported is invisible
to migrations, which shows up as a mysteriously empty revision.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
