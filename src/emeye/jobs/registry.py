# SPDX-License-Identifier: AGPL-3.0-or-later
"""Explicit job registration.

Explicit over import-scanning: a job that fails to import should be a loud
error, not a job that silently does not exist. A collector that quietly
vanishes is indistinguishable from one that ran and found nothing — and given
that chart data cannot be re-fetched, that is a difference worth a crash.
"""

from __future__ import annotations

from emeye.jobs.base import IngestJob

_REGISTRY: dict[str, type[IngestJob]] = {}


def register_job(cls: type[IngestJob]) -> type[IngestJob]:
    """Class decorator adding a job to the registry."""
    key = f"{cls.source}.{cls.job_name}"
    existing = _REGISTRY.get(key)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"duplicate job key '{key}': {existing.__name__} and {cls.__name__}. "
            f"Two jobs sharing a key would make ingest_run history ambiguous."
        )
    _REGISTRY[key] = cls
    return cls


def get_job(key: str) -> type[IngestJob]:
    """Look up a job class, or raise listing what is available."""
    try:
        return _REGISTRY[key]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(none registered)"
        raise KeyError(f"unknown job '{key}'. Available: {available}") from None


def list_jobs() -> dict[str, type[IngestJob]]:
    """Every registered job, keyed by '<source>.<job_name>'."""
    return dict(sorted(_REGISTRY.items()))


def clear_registry() -> None:
    """Reset the registry. For tests only."""
    _REGISTRY.clear()
