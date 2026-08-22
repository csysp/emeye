# SPDX-License-Identifier: AGPL-3.0-or-later
"""The only writer to ``raw_document``.

Everything that lands a payload goes through here, so bronze's invariants live
in one reviewable place rather than being restated (and eventually mis-stated)
in every connector.

There are deliberately no update or delete helpers. Not discouraged — absent,
so there is nothing to call by accident. The database enforces the same rule
with a trigger; this module is the layer that makes the rule obvious.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from emeye.db.engine import session_scope
from emeye.db.models import RawDocument
from emeye.logging import get_logger

log = get_logger(__name__)


def canonical_params_hash(params: dict[str, Any] | None) -> str:
    """Stable hash of request parameters.

    Canonical JSON with sorted keys, so ``{"a": 1, "b": 2}`` and
    ``{"b": 2, "a": 1}`` hash identically. The unique index keys on this rather
    than on the JSONB column, which would otherwise make uniqueness depend on
    JSONB equality semantics.
    """
    canonical = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def content_hash(body: bytes) -> str:
    """sha256 of the bytes exactly as received."""
    return hashlib.sha256(body).hexdigest()


def store_document(
    *,
    source: str,
    endpoint: str,
    url: str,
    http_status: int,
    body: bytes,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    raw_body: str | None = None,
    content_type: str | None = None,
    elapsed_ms: int | None = None,
    fetched_at: datetime | None = None,
) -> int:
    """Append one document to bronze. Returns its id.

    ``payload`` is the extracted JSON; ``raw_body`` is the surrounding markup
    when the source shipped HTML. Storing both keeps bronze replayable when the
    *extraction* was wrong, not merely the parse.
    """
    when = fetched_at or datetime.now(UTC)
    digest = content_hash(body)
    params_hash = canonical_params_hash(params)

    with session_scope() as session:
        document = RawDocument(
            source=source,
            endpoint=endpoint,
            params=params or {},
            params_hash=params_hash,
            url=url,
            fetched_at=when,
            http_status=http_status,
            payload=payload,
            raw_body=raw_body,
            content_hash=digest,
            content_type=content_type,
            elapsed_ms=elapsed_ms,
        )
        session.add(document)
        session.flush()
        document_id = document.id

    log.info(
        "bronze_stored",
        source=source,
        endpoint=endpoint,
        http_status=http_status,
        content_hash=digest[:12],
        bytes=len(body),
        document_id=document_id,
    )
    return document_id


def latest_document(
    source: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> RawDocument | None:
    """Most recent document for a request shape, or None."""
    params_hash = canonical_params_hash(params)
    with session_scope() as session:
        statement = (
            select(RawDocument)
            .where(
                RawDocument.source == source,
                RawDocument.endpoint == endpoint,
                RawDocument.params_hash == params_hash,
            )
            .order_by(RawDocument.fetched_at.desc())
            .limit(1)
        )
        document = session.execute(statement).scalar_one_or_none()
        if document is not None:
            session.expunge(document)
        return document


def has_content(digest: str) -> bool:
    """Whether this exact content has ever been stored.

    Used for the cache check. Note this asks about *content*, not about a
    request: identical content fetched on two days is still two rows, because
    each is a separate fact about that day.
    """
    with session_scope() as session:
        statement = select(RawDocument.id).where(RawDocument.content_hash == digest).limit(1)
        return session.execute(statement).scalar_one_or_none() is not None


def iter_documents(
    source: str,
    endpoint: str | None = None,
    since: datetime | None = None,
) -> Iterator[RawDocument]:
    """Replay documents in deterministic order. The reparse path.

    Ordered by ``(fetched_at, id)`` so a reparse produces the same result every
    time, which is what makes "fix the parser and re-run" a reliable operation
    rather than a hopeful one.
    """
    with session_scope() as session:
        statement = select(RawDocument).where(RawDocument.source == source)
        if endpoint is not None:
            statement = statement.where(RawDocument.endpoint == endpoint)
        if since is not None:
            statement = statement.where(RawDocument.fetched_at >= since)
        statement = statement.order_by(RawDocument.fetched_at, RawDocument.id)

        for document in session.execute(statement).scalars():
            session.expunge(document)
            yield document
