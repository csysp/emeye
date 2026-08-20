# SPDX-License-Identifier: AGPL-3.0-or-later
"""emeye CLI entrypoint.

emeye  Copyright (C) 2026  emeye contributors
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it under the terms
of the GNU Affero General Public License v3 or later; see the LICENSE file.
"""

from __future__ import annotations

import typer

from emeye import __version__
from emeye.cli.groups import register_all
from emeye.config import get_settings
from emeye.logging import configure_logging

app = typer.Typer(
    name="emeye",
    help="Electronic Music Eye — longitudinal trend analysis for electronic/club music.",
    no_args_is_help=True,
    add_completion=False,
)

register_all(app)

LICENSE_NOTICE = (
    "emeye  Copyright (C) 2026  emeye contributors\n"
    "License AGPL-3.0-or-later: GNU Affero GPL version 3 or later\n"
    "<https://www.gnu.org/licenses/agpl-3.0.html>\n"
    "This is free software: you are free to change and redistribute it.\n"
    "There is NO WARRANTY, to the extent permitted by law."
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"emeye {__version__}")
        typer.echo()
        typer.echo(LICENSE_NOTICE)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: ARG001 - consumed by the eager callback above
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and license, then exit.",
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Raise log level to DEBUG."),
) -> None:
    """Configure the process before dispatching to a command group."""
    settings = get_settings()
    if verbose:
        settings = settings.model_copy(update={"log_level": "DEBUG"})
    configure_logging(settings)


if __name__ == "__main__":  # pragma: no cover
    app()
