# SPDX-License-Identifier: AGPL-3.0-or-later
"""Job contract, registry and runner bookkeeping."""

from __future__ import annotations

from typing import Any

import pytest

from emeye.config import Settings
from emeye.jobs.base import IngestJob, JobContext, JobResult
from emeye.jobs.registry import clear_registry, get_job, list_jobs, register_job

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()


def _settings(**extra: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x",
        "user_agent": "emeye-test/0.0 (+mailto:t@example.invalid)",
    }
    return Settings(**{**base, **extra})  # type: ignore[arg-type]


class _Demo(IngestJob):
    source = "demo"
    job_name = "sample"

    def run(self, context: JobContext) -> JobResult:  # noqa: ARG002
        return JobResult(items_fetched=1, items_written=1, cache_misses=1)


def test_abstract_job_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        IngestJob()  # type: ignore[abstract]


def test_subclass_must_declare_source_and_name() -> None:
    with pytest.raises(TypeError, match="source"):

        class Missing(IngestJob):
            job_name = "x"

            def run(self, context: JobContext) -> JobResult:  # noqa: ARG002
                return JobResult()


def test_key_combines_source_and_name() -> None:
    assert _Demo().key == "demo.sample"


def test_register_and_retrieve() -> None:
    register_job(_Demo)
    assert get_job("demo.sample") is _Demo
    assert "demo.sample" in list_jobs()


def test_duplicate_key_raises() -> None:
    """Two jobs sharing a key would make ingest_run history ambiguous."""
    register_job(_Demo)

    class Other(IngestJob):
        source = "demo"
        job_name = "sample"

        def run(self, context: JobContext) -> JobResult:  # noqa: ARG002
            return JobResult()

    with pytest.raises(ValueError, match="duplicate job key"):
        register_job(Other)


def test_registering_the_same_class_twice_is_idempotent() -> None:
    register_job(_Demo)
    register_job(_Demo)
    assert len(list_jobs()) == 1


def test_unknown_job_lists_what_is_available() -> None:
    register_job(_Demo)
    with pytest.raises(KeyError, match=r"demo\.sample"):
        get_job("nope.missing")


def test_result_reports_whether_network_was_used() -> None:
    assert JobResult(cache_misses=1).used_network is True
    assert JobResult(cache_hits=3).used_network is False


def test_disabled_source_refuses_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """And records nothing: an attempt that never happened must not appear
    in status as though collection were occurring."""
    from emeye.jobs import runner

    register_job(_Demo)
    opened: list[Any] = []
    monkeypatch.setattr(runner, "_open_run", lambda *a, **_kw: opened.append(a) or 1)

    with pytest.raises(runner.SourceDisabledError, match="demo"):
        runner.run_job("demo.sample", settings=_settings())
    assert opened == []
