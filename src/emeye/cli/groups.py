# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command groups.

The surface mirrors the roadmap deliberately: someone running ``emeye --help``
on day one should be able to see where the project is going. Each group is
registered now and filled in by the phase named in ``DELIVERED_BY``.
"""

from __future__ import annotations

import typer

# Group name -> (help text, roadmap phase that implements it)
GROUPS: dict[str, tuple[str, int]] = {
    "ingest": ("Collect from upstream sources into bronze", 3),
    "enrich": ("Cross-reference and resolve entities across sources", 4),
    "dbt": ("Build and test the silver/gold transformation models", 6),
    "forecast": ("Fit, backtest and score trend forecasts", 7),
    "export": ("Dump marts to Parquet/CSV for DuckDB and notebooks", 8),
    "status": ("Report ingest health, coverage and backup age", 2),
    "backup": ("Write a portable warehouse dump for manual offline copy", 8),
}


def not_implemented(group: str, phase: int) -> typer.Exit:
    """Report an unimplemented group and return an exit with code 2.

    Exit code 2, never 0: a stub that succeeds silently is the most dangerous
    thing in a CLI, because a scheduler will treat it as a completed job.
    """
    typer.secho(
        f"'emeye {group}' is not implemented yet — delivered in phase {phase}. "
        f"See .planning/ROADMAP.md",
        fg=typer.colors.YELLOW,
        err=True,
    )
    return typer.Exit(code=2)


def build_group(name: str, help_text: str, phase: int) -> typer.Typer:
    """Build a sub-app with a placeholder command that fails honestly."""
    app = typer.Typer(name=name, help=help_text, no_args_is_help=True)

    @app.command("run", help=f"Not implemented yet — delivered in phase {phase}.")
    def run() -> None:
        raise not_implemented(name, phase)

    return app


def register_all(parent: typer.Typer) -> None:
    """Attach every group to the root app."""
    for name, (help_text, phase) in GROUPS.items():
        parent.add_typer(build_group(name, help_text, phase), name=name)
