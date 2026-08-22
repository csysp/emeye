# SPDX-License-Identifier: AGPL-3.0-or-later
"""``emeye status`` — is collection actually happening?

A collection system whose health you cannot see is one you silently stop
trusting. Given that chart data is irrecoverable, a gap noticed six months late
is six months never captured.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from emeye.db.engine import check_connection, session_scope
from emeye.db.models import IngestRun
from emeye.jobs.runner import (
    STATUS_FAILED,
    STATUS_SKIPPED_CACHE,
    STATUS_STARTED,
    STATUS_SUCCEEDED,
    find_stale_runs,
)

app = typer.Typer(name="status", help="Report ingest health, coverage and backup age")
console = Console()

STALE_AFTER = timedelta(hours=6)

_STATUS_STYLE = {
    STATUS_SUCCEEDED: "[green]succeeded[/green]",
    STATUS_SKIPPED_CACHE: "[cyan]skipped_cache[/cyan]",
    STATUS_FAILED: "[red]failed[/red]",
    STATUS_STARTED: "[yellow]started[/yellow]",
}


def _latest_per_source() -> list[IngestRun]:
    with session_scope() as session:
        newest = (
            select(IngestRun.source, func.max(IngestRun.started_at).label("latest"))
            .group_by(IngestRun.source)
            .subquery()
        )
        statement = select(IngestRun).join(
            newest,
            (IngestRun.source == newest.c.source) & (IngestRun.started_at == newest.c.latest),
        )
        runs = list(session.execute(statement).scalars())
        for run in runs:
            session.expunge(run)
        return runs


@app.callback(invoke_without_command=True)
def status() -> None:
    """Show the most recent run per source."""
    if not check_connection():
        console.print("[red]warehouse unreachable[/red] — is it running? try `make up`")
        raise typer.Exit(code=1)

    runs = _latest_per_source()
    if not runs:
        console.print("[yellow]No ingest runs recorded yet.[/yellow]")
        console.print("[dim]Nothing has been collected. Chart history is not backfillable.[/dim]")
        raise typer.Exit(code=0)

    table = Table(title="Ingest health")
    for column in ("Source", "Job", "Status", "Last run", "Fetched", "Written", "Cache hit rate"):
        table.add_column(column)

    for run in sorted(runs, key=lambda r: r.source):
        total = run.cache_hits + run.cache_misses
        hit_rate = f"{run.cache_hits / total:.0%}" if total else "—"
        age = datetime.now(UTC) - run.started_at
        table.add_row(
            run.source,
            run.job_name,
            _STATUS_STYLE.get(run.status, run.status),
            f"{_humanise(age)} ago",
            str(run.items_fetched),
            str(run.items_written),
            hit_rate,
        )
    console.print(table)

    for run in runs:
        if run.status == STATUS_FAILED and run.error_message:
            console.print(f"[red]{run.source}:[/red] {run.error_message}")

    stale = find_stale_runs(STALE_AFTER)
    if stale:
        console.print(
            f"\n[yellow]{len(stale)} run(s) still marked 'started' after "
            f"{STALE_AFTER}. That means a process died mid-run — treat as suspicious, "
            f"not as in-progress.[/yellow]"
        )
        raise typer.Exit(code=1)

    if any(run.status == STATUS_FAILED for run in runs):
        raise typer.Exit(code=1)


def _humanise(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"
