# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ingest jobs: the contract, the registry, and the runner that tracks them."""

from __future__ import annotations

from emeye.jobs.base import IngestJob, JobContext, JobResult
from emeye.jobs.registry import get_job, list_jobs, register_job
from emeye.jobs.runner import find_stale_runs, run_job

__all__ = [
    "IngestJob",
    "JobContext",
    "JobResult",
    "find_stale_runs",
    "get_job",
    "list_jobs",
    "register_job",
    "run_job",
]
