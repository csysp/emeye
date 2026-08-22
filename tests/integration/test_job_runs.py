# SPDX-License-Identifier: AGPL-3.0-or-later
"""Runner bookkeeping against a live database."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from emeye.config import Settings, get_settings
from emeye.db.engine import check_connection, get_engine, session_scope
from emeye.db.models import IngestRun
from emeye.jobs.base import IngestJob, JobContext, JobResult
from emeye.jobs.registry import clear_registry, register_job
from emeye.jobs.runner import (
    STATUS_FAILED,
    STATUS_SKIPPED_CACHE,
    STATUS_SUCCEEDED,
    find_stale_runs,
    run_job,
)

pytestmark = [pytest.mark.integration]


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
        conn.execute(text("delete from ingest_run where source = 'demo'"))


def _enabled() -> Settings:
    """Real settings with the declared demo source switched on."""
    return get_settings().model_copy(update={"enable_demo": True})


def _latest(source: str) -> IngestRun:
    with session_scope() as session:
        run = (
            session.query(IngestRun)
            .filter(IngestRun.source == source)
            .order_by(IngestRun.started_at.desc())
            .first()
        )
        assert run is not None
        session.expunge(run)
        return run


def _register(name: str, result: JobResult | None = None, boom: bool = False) -> None:
    class Job(IngestJob):
        source = "demo"
        job_name = name

        def run(self, context: JobContext) -> JobResult:  # noqa: ARG002
            if boom:
                raise ValueError("deliberate failure")
            return result or JobResult(items_fetched=2, items_written=2, cache_misses=2)

    register_job(Job)


def test_successful_run_is_recorded() -> None:
    _register("ok")
    run_job("demo.ok", settings=_enabled())

    run = _latest("demo")
    assert run.status == STATUS_SUCCEEDED
    assert run.items_fetched == 2
    assert run.finished_at is not None


def test_fully_cached_run_records_skipped_cache() -> None:
    """This is how 'one fetch per chart per reset' becomes provable."""
    _register("cached", JobResult(items_fetched=0, cache_hits=3, cache_misses=0))
    run_job("demo.cached", settings=_enabled())
    assert _latest("demo").status == STATUS_SKIPPED_CACHE


def test_failure_is_recorded_and_reraised() -> None:
    _register("boom", boom=True)
    with pytest.raises(ValueError, match="deliberate failure"):
        run_job("demo.boom", settings=_enabled())

    run = _latest("demo")
    assert run.status == STATUS_FAILED
    assert run.error_type == "ValueError"
    assert "deliberate failure" in (run.error_message or "")
    assert run.traceback


def test_failure_record_survives_the_failure() -> None:
    """The failure row is written in its own transaction.

    A failure record rolled back with the work that failed is worse than
    useless — status would show nothing happened.
    """
    _register("boom2", boom=True)
    with pytest.raises(ValueError):
        run_job("demo.boom2", settings=_enabled())
    assert _latest("demo").status == STATUS_FAILED


def test_stale_started_runs_are_findable() -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "insert into ingest_run (source, job_name, status, started_at) "
                "values ('demo', 'crashed', 'started', now() - interval '2 days')"
            )
        )
    stale = find_stale_runs(timedelta(hours=6))
    assert any(r.source == "demo" and r.job_name == "crashed" for r in stale)
