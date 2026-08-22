# SPDX-License-Identifier: AGPL-3.0-or-later
"""Runs jobs and records what happened.

All ``ingest_run`` bookkeeping lives here rather than in the jobs, so a job
physically cannot forget to record itself.
"""

from __future__ import annotations

import time
import traceback as traceback_module
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from emeye.config import Settings, get_settings
from emeye.db.engine import session_scope
from emeye.db.models import IngestRun
from emeye.jobs.base import JobContext, JobResult
from emeye.jobs.registry import get_job
from emeye.logging import get_logger

log = get_logger(__name__)

STATUS_STARTED = "started"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_SKIPPED_CACHE = "skipped_cache"


class SourceDisabledError(RuntimeError):
    """Raised when a job's source is switched off."""


def _open_run(source: str, job_name: str, params: dict[str, Any]) -> int:
    """Record the attempt before it happens, in its own transaction.

    A crashed process must leave a ``started`` row rather than no evidence at
    all: silence is indistinguishable from "never scheduled", and given that
    chart snapshots cannot be re-fetched, that is a distinction worth storing.
    """
    with session_scope() as session:
        run = IngestRun(
            source=source,
            job_name=job_name,
            status=STATUS_STARTED,
            started_at=datetime.now(UTC),
            params=params,
        )
        session.add(run)
        session.flush()
        return run.id


def _close_run(run_id: int, **values: Any) -> None:
    """Finalise a run row in its own transaction.

    Separate from the job's own work on purpose: a failure record rolled back
    together with the failure that caused it is worse than useless.
    """
    with session_scope() as session:
        run = session.get(IngestRun, run_id)
        if run is None:  # pragma: no cover - only if the row was removed underneath us
            return
        for key, value in values.items():
            setattr(run, key, value)
        run.finished_at = datetime.now(UTC)


def run_job(key: str, settings: Settings | None = None, **params: Any) -> int:
    """Run one job by key, returning its ``ingest_run`` id."""
    settings = settings or get_settings()
    job_class = get_job(key)
    source = job_class.source

    if not getattr(settings, f"enable_{source}", False):
        # No run row: it did not run. Recording an attempt that never happened
        # would make `emeye status` misleading in exactly the direction that
        # matters — appearing to collect when nothing is being collected.
        raise SourceDisabledError(
            f"source '{source}' is disabled; set EMEYE_ENABLE_{source.upper()}=true to enable it"
        )

    run_id = _open_run(source, job_class.job_name, params)
    started = time.monotonic()
    log.info("job_started", job=key, source=source, run_id=run_id, params=params)

    try:
        result: JobResult = job_class().run(JobContext(settings=settings, params=params))
    except Exception as exc:
        _close_run(
            run_id,
            status=STATUS_FAILED,
            error_type=type(exc).__name__,
            error_message=str(exc)[:4000],
            traceback=traceback_module.format_exc()[:8000],
        )
        log.error(
            "job_failed",
            job=key,
            source=source,
            run_id=run_id,
            error_type=type(exc).__name__,
            error=str(exc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise

    # Everything served from bronze means we correctly declined to re-fetch.
    # Recording that distinctly is what makes the "one fetch per reset"
    # invariant provable instead of assumed.
    status = (
        STATUS_SKIPPED_CACHE
        if result.cache_misses == 0 and result.cache_hits > 0
        else STATUS_SUCCEEDED
    )

    _close_run(
        run_id,
        status=status,
        items_fetched=result.items_fetched,
        items_written=result.items_written,
        cache_hits=result.cache_hits,
        cache_misses=result.cache_misses,
    )
    log.info(
        "job_finished",
        job=key,
        source=source,
        run_id=run_id,
        status=status,
        items_fetched=result.items_fetched,
        items_written=result.items_written,
        cache_hits=result.cache_hits,
        cache_misses=result.cache_misses,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    return run_id


def find_stale_runs(older_than: timedelta) -> list[IngestRun]:
    """Runs still marked ``started`` past a threshold — i.e. crashed processes."""
    cutoff = datetime.now(UTC) - older_than
    with session_scope() as session:
        statement = (
            select(IngestRun)
            .where(IngestRun.status == STATUS_STARTED, IngestRun.started_at < cutoff)
            .order_by(IngestRun.started_at)
        )
        runs = list(session.execute(statement).scalars())
        for run in runs:
            session.expunge(run)
        return runs
