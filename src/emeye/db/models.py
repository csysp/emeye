# SPDX-License-Identifier: AGPL-3.0-or-later
"""ORM models.

Phase 1 defined ``schema_meta``. Phase 2 adds the bronze layer: ``raw_document``
(immutable landing zone) and ``ingest_run`` (what happened, when, and whether it
worked). Silver and gold arrive later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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


class RawDocument(Base):
    """One fetched document, exactly as received. Append-only.

    This is the layer the project's value rests on. Charts are irrecoverable:
    if a payload is captured wrongly or mutated later, no downstream fix gets it
    back. Everything else in emeye is rebuildable from these rows.

    UPDATE and DELETE are rejected by a database trigger, not merely by
    convention — see migration 0002.
    """

    __tablename__ = "raw_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    # sha256 of canonical-JSON params. The unique index keys on this rather than
    # on `params` itself, so uniqueness does not depend on JSONB equality
    # semantics or key ordering.
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    http_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Extracted JSON. Beatport ships HTML with embedded JSON; the JSON lands
    # here and the surrounding markup in raw_body, so bronze stays replayable
    # when the *extraction* was wrong and not merely the parse.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        # fetched_at is part of the key on purpose: the same chart content on
        # two days is two facts. Keying on content alone would silently collapse
        # the chart time series, which is the one thing we cannot rebuild.
        UniqueConstraint(
            "source",
            "endpoint",
            "params_hash",
            "fetched_at",
            name="uq_raw_document_request",
        ),
        Index("ix_raw_document_latest", "source", "endpoint", "fetched_at"),
        # Deliberately NOT unique — see above.
        Index("ix_raw_document_content_hash", "content_hash"),
    )


class IngestRun(Base):
    """One execution of one job.

    Written before the work starts and updated on completion, so a crashed
    process leaves a ``started`` row rather than no evidence at all. Silence is
    indistinguishable from "never scheduled", and given that chart data is
    irrecoverable, that difference matters.
    """

    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_written: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cache_misses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (Index("ix_ingest_run_recent", "source", "started_at"),)
