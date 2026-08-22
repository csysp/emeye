# SPDX-License-Identifier: AGPL-3.0-or-later
"""The job contract.

A job says what it is and does the work. It does **not** touch ``ingest_run`` —
the runner owns that bookkeeping, so a job cannot forget to record itself, and
every job is observable on the same terms without each author remembering to
make it so.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from emeye.config import Settings


@dataclass
class JobResult:
    """What a job did.

    ``cache_hits`` is not decoration: a run whose fetches were all served from
    bronze is recorded as ``skipped_cache``, which is how the "one fetch per
    chart per reset" invariant is proved rather than assumed.
    """

    items_fetched: int = 0
    items_written: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def used_network(self) -> bool:
        return self.cache_misses > 0


@dataclass
class JobContext:
    """What a job is given to work with."""

    settings: Settings
    params: dict[str, Any] = field(default_factory=dict)


class IngestJob(ABC):
    """One unit of collection.

    Subclasses set ``source`` and ``job_name`` and implement ``run``.
    """

    source: str
    job_name: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return
        for attribute in ("source", "job_name"):
            if not getattr(cls, attribute, None):
                raise TypeError(f"{cls.__name__} must define a non-empty '{attribute}'")

    @property
    def key(self) -> str:
        return f"{self.source}.{self.job_name}"

    @abstractmethod
    def run(self, context: JobContext) -> JobResult:
        """Do the work and report what happened."""
