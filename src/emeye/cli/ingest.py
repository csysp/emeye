# SPDX-License-Identifier: AGPL-3.0-or-later
"""``emeye ingest`` — run collectors and replay bronze."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from emeye.bronze import iter_documents
from emeye.config import get_settings
from emeye.jobs.registry import list_jobs
from emeye.jobs.runner import SourceDisabledError, run_job
from emeye.logging import get_logger

app = typer.Typer(
    name="ingest", help="Collect from upstream sources into bronze", no_args_is_help=True
)
console = Console()
log = get_logger(__name__)


@app.command("list")
def list_registered() -> None:
    """List registered jobs and whether their source is enabled."""
    settings = get_settings()
    jobs = list_jobs()
    if not jobs:
        console.print("[yellow]No jobs registered.[/yellow]")
        return

    table = Table(title="Registered ingest jobs")
    table.add_column("Job")
    table.add_column("Source")
    table.add_column("Enabled")

    for key, job_class in jobs.items():
        enabled = getattr(settings, f"enable_{job_class.source}", False)
        table.add_row(
            key,
            job_class.source,
            "[green]yes[/green]" if enabled else "[dim]no[/dim]",
        )
    console.print(table)


@app.command("run")
def run(job: str = typer.Argument(..., help="Job key, e.g. 'beatport.top100'")) -> None:
    """Run one job."""
    try:
        run_id = run_job(job)
    except SourceDisabledError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=3) from exc
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]done[/green] — ingest_run id {run_id}")


@app.command("reparse")
def reparse(
    source: str = typer.Argument(..., help="Source to replay from bronze"),
    endpoint: str | None = typer.Option(None, help="Restrict to one endpoint"),
) -> None:
    """Rebuild from bronze alone, without touching the network.

    This is the guarantee that makes a wrong parser a cheap mistake rather than
    lost data. It constructs no HTTP client at all — not merely 'does not need
    the network', but cannot reach it.
    """
    count = 0
    for _document in iter_documents(source, endpoint=endpoint):
        count += 1

    log.info("reparse_complete", source=source, endpoint=endpoint, documents=count)
    console.print(f"replayed [bold]{count}[/bold] bronze document(s) for [bold]{source}[/bold]")
    if count == 0:
        console.print("[dim]nothing in bronze for that source yet[/dim]")
