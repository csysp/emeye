# SPDX-License-Identifier: AGPL-3.0-or-later
"""Structured logging.

Key/value logs to stdout: human-readable on a TTY, JSON when piped. The
container runtime owns log persistence, so nothing here writes to a file.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from emeye.config import Settings

_configured = False


def configure_logging(settings: Settings) -> None:
    """Configure structlog once per process.

    Idempotent: calling this more than once (the CLI callback, a test fixture,
    a worker entrypoint) must not duplicate handlers or double-render lines.
    """
    global _configured
    if _configured:
        return

    as_json = settings.log_json
    if as_json is None:
        as_json = not sys.stderr.isatty()

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if as_json
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    level = getattr(logging, str(settings.log_level).upper(), logging.INFO)

    # force=True is load-bearing: basicConfig is a no-op when the root logger
    # already has handlers, so without it this function silently does nothing
    # whenever anything else configured logging first (pytest, a library, an
    # embedding host) — and the app would log at the wrong level, to the wrong
    # stream, in the wrong format, with no error to show for it.
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=settings.service_name)
    _configured = True


def reset_logging() -> None:
    """Clear the configured flag. For tests only."""
    global _configured
    _configured = False
    structlog.contextvars.clear_contextvars()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for ``name``."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
