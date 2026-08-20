# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail when the Makefile and make.ps1 stop offering the same targets.

Two task runners is a deliberate trade: it buys native Windows and Linux
support without a host-level runtime, at the cost of a place where drift can
hide. A target added to one and forgotten in the other means the documented
workflow silently stops working on half the supported platforms — and nobody
notices until someone on that platform tries it.

This makes the divergence a build failure instead of a bug report.

Usage:
    python scripts/check_task_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"
PS_RUNNER = REPO / "make.ps1"

# Makefile-only mechanics that are not user-facing targets.
MAKEFILE_IGNORE = {".env"}


def makefile_targets(text: str) -> set[str]:
    """Targets declared in .PHONY — the authoritative list."""
    phony = re.search(r"^\.PHONY:\s*(.+)$", text, re.MULTILINE)
    if not phony:
        raise SystemExit("Makefile has no .PHONY line; cannot determine targets")
    declared = set(phony.group(1).split())

    # Cross-check that every .PHONY target actually has a rule.
    rules = set(re.findall(r"^([a-zA-Z][a-zA-Z0-9_-]*):", text, re.MULTILINE)) - MAKEFILE_IGNORE
    missing_rules = declared - rules
    if missing_rules:
        raise SystemExit(
            f"declared in .PHONY but no rule defined: {', '.join(sorted(missing_rules))}"
        )
    return declared


def powershell_targets(text: str) -> set[str]:
    """Targets handled by the switch statement in make.ps1."""
    body = text.split("switch ($Target.ToLower())", 1)
    if len(body) == 1:
        raise SystemExit("make.ps1 has no switch on $Target; cannot determine targets")

    found: set[str] = set()
    for line in body[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("default"):
            continue
        # Match: 'name' {   or   'a' { ... }
        match = re.match(r"^'([a-z0-9_-]+)'\s*\{", stripped)
        if match:
            found.add(match.group(1))
    return found


def powershell_help_targets(text: str) -> set[str]:
    """Targets listed in make.ps1's help output."""
    block = re.search(r"\$targets = \[ordered\]@\{(.*?)\n\s*\}", text, re.DOTALL)
    if not block:
        raise SystemExit("make.ps1 help block not found")
    return set(re.findall(r"^\s*'([a-z0-9_-]+)'\s*=", block.group(1), re.MULTILINE))


def main() -> int:
    make_text = MAKEFILE.read_text(encoding="utf-8")
    ps_text = PS_RUNNER.read_text(encoding="utf-8")

    make_set = makefile_targets(make_text)
    ps_set = powershell_targets(ps_text)
    ps_help = powershell_help_targets(ps_text)

    failed = False

    only_make = sorted(make_set - ps_set)
    only_ps = sorted(ps_set - make_set)
    if only_make:
        failed = True
        print(f"In Makefile but NOT in make.ps1: {', '.join(only_make)}", file=sys.stderr)
        print("  -> Windows users cannot run these.", file=sys.stderr)
    if only_ps:
        failed = True
        print(f"In make.ps1 but NOT in the Makefile: {', '.join(only_ps)}", file=sys.stderr)
        print("  -> Linux/macOS users cannot run these.", file=sys.stderr)

    undocumented = sorted(ps_set - ps_help)
    if undocumented:
        failed = True
        print(
            f"Handled by make.ps1 but missing from its help: {', '.join(undocumented)}",
            file=sys.stderr,
        )

    if failed:
        print(
            "\nFAIL — the two task runners have diverged. Every user-facing target must "
            "exist in both, so the documented workflow works on every supported platform.",
            file=sys.stderr,
        )
        return 1

    print(f"OK — {len(make_set)} targets, identical in Makefile and make.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
