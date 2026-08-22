# SPDX-License-Identifier: AGPL-3.0-or-later
"""The single outbound HTTP path.

Rate limiting, robots.txt, retry/backoff and per-source gating are enforced
here rather than in each connector. A rule applied per-source is a rule that
will eventually be forgotten in one source.

Nothing outside this package may construct an httpx client; a test enforces it.
"""

from __future__ import annotations

from emeye.http.client import FetchResult, PoliteClient, RobotsDenied, SourceDisabled
from emeye.http.limiter import RateLimiter
from emeye.http.robots import RobotsPolicy

__all__ = [
    "FetchResult",
    "PoliteClient",
    "RateLimiter",
    "RobotsDenied",
    "RobotsPolicy",
    "SourceDisabled",
]
