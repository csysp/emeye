# SPDX-License-Identifier: AGPL-3.0-or-later
"""REQ-17: running a job twice changes no row counts.

Not 'roughly the same'. Identical. A collector that quietly double-writes
inflates every count downstream, and the inflation is indistinguishable from
real growth in a trend series.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text

from emeye.bronze import content_hash, has_content, store_document
from emeye.config import get_settings
from emeye.db.engine import check_connection, get_engine, session_scope
from emeye.db.models import RawDocument
from emeye.jobs.base import IngestJob, JobContext, JobResult
from emeye.jobs.registry import clear_registry, register_job
from emeye.jobs.runner import STATUS_SKIPPED_CACHE, run_job

pytestmark = [pytest.mark.integration]

BODY = b'{"chart": "top100", "tracks": [{"id": 1}]}'


@pytest.fixture(scope="module", autouse=True)
def _require_database() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    if not check_connection():
        pytest.skip("no PostgreSQL reachable — start it with `make up`", allow_module_level=True)


@pytest.fixture(autouse=True)
def _clean() -> None:
    clear_registry()
    with get_engine().begin() as conn:
        conn.execute(text("alter table raw_document disable trigger raw_document_append_only"))
        conn.execute(text("delete from raw_document where source = 'demo'"))
        conn.execute(text("alter table raw_document enable trigger raw_document_append_only"))
        conn.execute(text("delete from ingest_run where source = 'demo'"))


def _document_count() -> int:
    with session_scope() as session:
        return session.execute(
            select(func.count()).select_from(RawDocument).where(RawDocument.source == "demo")
        ).scalar_one()


class CachingJob(IngestJob):
    """Writes once, then declines to write the same content again.

    This is the shape every real collector takes: check bronze first, and a
    cache hit is always preferred over a request.
    """

    source = "demo"
    job_name = "idempotent"

    def run(self, context: JobContext) -> JobResult:  # noqa: ARG002
        digest = content_hash(BODY)
        if has_content(digest):
            return JobResult(cache_hits=1, cache_misses=0)

        store_document(
            source="demo",
            endpoint="charts/top100",
            url="https://example.invalid/charts/top100",
            http_status=200,
            body=BODY,
            params={"chart": "top100"},
            payload={"chart": "top100"},
        )
        return JobResult(items_fetched=1, items_written=1, cache_misses=1)


def test_second_run_writes_nothing_new() -> None:
    register_job(CachingJob)
    settings = get_settings().model_copy(update={"enable_demo": True})

    run_job("demo.idempotent", settings=settings)
    after_first = _document_count()

    run_job("demo.idempotent", settings=settings)
    after_second = _document_count()

    assert after_first == 1
    assert after_second == after_first, "second run must not add a row"


def test_second_run_is_recorded_as_skipped_cache() -> None:
    """The evidence that the cache was used, rather than a claim that it was."""
    register_job(CachingJob)
    settings = get_settings().model_copy(update={"enable_demo": True})

    run_job("demo.idempotent", settings=settings)
    second_id = run_job("demo.idempotent", settings=settings)

    with session_scope() as session:
        from emeye.db.models import IngestRun

        run = session.get(IngestRun, second_id)
        assert run is not None
        assert run.status == STATUS_SKIPPED_CACHE
        assert run.cache_hits == 1
