# SPDX-License-Identifier: AGPL-3.0-or-later
"""ORM models.

Phase 1 defines only ``schema_meta`` — enough to prove the migration loop end
to end. Bronze, silver and gold tables arrive in phase 2 onward.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from emeye.db.base import Base


class SchemaMeta(Base):
    """Key/value facts about the warehouse itself.

    Not application data: this records things like when the schema was
    initialized and, from phase 8, when the last backup was taken — which is
    what lets ``emeye status`` surface a stale-backup warning.
    """

    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
