# SPDX-License-Identifier: AGPL-3.0-or-later
"""emeye — Electronic Music Eye.

A personal, local-first warehouse and forecasting toolkit for electronic and
club music production trends.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("emeye")
except PackageNotFoundError:  # pragma: no cover - only when running from a bare tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
