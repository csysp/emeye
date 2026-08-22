# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bronze against a live database.

The append-only guarantee is tested against the real trigger rather than
trusted, because it is the invariant that makes every parse replayable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, text, update

from emeye.bronze import (
    content_hash,
    has_content,
    iter_documents,
    latest_document,
    store_document,
)
from emeye.config import get_settings
from emeye.db.engine import check_connection, get_engine, session_scope
from emeye.db.models import RawDocument

pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module", autouse=True)
def _require_database() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    if not check_connection():
        pytest.skip("no PostgreSQL reachable — start it with `make up`", allow_module_level=True)


@pytest.fixture(autouse=True)
def _clean_bronze() -> None:
    """Remove test rows.

    The trigger blocks DELETE, so this drops it for the duration — which is
    exactly the "drop it deliberately" escape hatch the migration documents.
    """
    with get_engine().begin() as conn:
        conn.execute(text("alter table raw_document disable trigger raw_document_append_only"))
        conn.execute(text("delete from raw_document where source like 'test%'"))
        conn.execute(text("alter table raw_document enable trigger raw_document_append_only"))


def _store(**overrides: object) -> int:
    defaults: dict[str, object] = {
        "source": "test_source",
        "endpoint": "charts/top100",
        "url": "https://example.invalid/charts/top100",
        "http_status": 200,
        "body": b'{"tracks": []}',
        "params": {"page": 1},
        "payload": {"tracks": []},
    }
    defaults.update(overrides)
    return store_document(**defaults)  # type: ignore[arg-type]


def test_document_round_trips() -> None:
    _store(payload={"tracks": [{"id": 1, "bpm": 128}]})
    document = latest_document("test_source", "charts/top100", {"page": 1})
    assert document is not None
    assert document.payload == {"tracks": [{"id": 1, "bpm": 128}]}
    assert document.http_status == 200


def test_update_is_rejected_by_the_database() -> None:
    """Append-only, enforced by the trigger and not by convention."""
    _store()
    with pytest.raises(Exception, match="append-only"), session_scope() as session:
        session.execute(
            update(RawDocument).where(RawDocument.source == "test_source").values(http_status=500)
        )


def test_delete_is_rejected_by_the_database() -> None:
    _store()
    with pytest.raises(Exception, match="append-only"), session_scope() as session:
        session.execute(delete(RawDocument).where(RawDocument.source == "test_source"))


def test_identical_content_on_two_dates_is_two_rows() -> None:
    """The regression test for the chart time series.

    A track's position on two consecutive days is two facts even when the
    payload bytes are identical. Deduplicating on content_hash would collapse
    them and destroy the only signal this project cannot re-fetch.
    """
    body = b'{"tracks": [{"id": 1}]}'
    yesterday = datetime.now(UTC) - timedelta(days=1)
    _store(body=body, fetched_at=yesterday)
    _store(body=body, fetched_at=datetime.now(UTC))

    documents = list(iter_documents("test_source"))
    assert len(documents) == 2
    assert documents[0].content_hash == documents[1].content_hash


def test_non_json_payload_round_trips_via_raw_body() -> None:
    html = "<html><body>no json here</body></html>"
    _store(body=html.encode(), payload=None, raw_body=html, content_type="text/html")
    document = latest_document("test_source", "charts/top100", {"page": 1})
    assert document is not None
    assert document.payload is None
    assert document.raw_body == html


def test_has_content_finds_a_stored_digest() -> None:
    body = b'{"unique": "payload-for-has-content"}'
    _store(body=body)
    assert has_content(content_hash(body)) is True
    assert has_content(content_hash(b"never stored")) is False


def test_latest_document_returns_the_newest() -> None:
    old = datetime.now(UTC) - timedelta(days=2)
    _store(body=b'{"v": 1}', payload={"v": 1}, fetched_at=old)
    _store(body=b'{"v": 2}', payload={"v": 2})
    document = latest_document("test_source", "charts/top100", {"page": 1})
    assert document is not None
    assert document.payload == {"v": 2}


def test_iter_documents_is_deterministically_ordered() -> None:
    now = datetime.now(UTC)
    for offset in (2, 0, 1):
        _store(
            body=f'{{"n": {offset}}}'.encode(),
            payload={"n": offset},
            fetched_at=now - timedelta(hours=offset),
        )
    order = [d.payload["n"] for d in iter_documents("test_source")]  # type: ignore[index]
    assert order == sorted(order, reverse=True)
