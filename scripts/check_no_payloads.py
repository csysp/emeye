# SPDX-License-Identifier: AGPL-3.0-or-later
"""Block secrets, third-party payloads and oversized files from being committed.

.gitignore is the first line of defence and it is easy to bypass with `git add
-f` or a path it does not cover. This is the mechanical backstop for REQ-24
(never redistribute third-party payloads) and REQ-25 (no credentials in the
repo): bronze data is collected under terms that permit personal analysis, not
publication, and a scraped payload pushed to a public remote is not something
that can be taken back.

Usage:
    python scripts/check_no_payloads.py            # staged files
    python scripts/check_no_payloads.py --all      # every tracked file
    python scripts/check_no_payloads.py f1 f2      # explicit paths
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 1_000_000

FORBIDDEN_SUFFIXES = {
    ".parquet",
    ".duckdb",
    ".sqlite",
    ".sqlite3",
    ".dump",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

FORBIDDEN_NAME_PARTS = (".sql.gz", ".sql.bz2", ".tar.gz.enc")

# Top-level directories whose contents are collected data, never source.
#
# Matched as path prefixes only. Matching the segment anywhere would flag
# src/emeye/bronze/ — which is the code that writes bronze, not bronze data.
FORBIDDEN_DIRS = ("data/", "exports/", "pgdata/", "bronze/")

# Source trees are never collected data, whatever they are named.
SOURCE_PREFIXES = ("src/", "tests/", "scripts/", "docker/", "dbt/", "app/")

# Large files that are legitimately part of the repo.
SIZE_ALLOWLIST = {"uv.lock", "LICENSE"}


def _git(*args: str) -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def staged_files() -> list[str]:
    return _git("diff", "--cached", "--name-only", "--diff-filter=ACM")


def tracked_files() -> list[str]:
    return _git("ls-files")


def check(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for raw in paths:
        path = Path(raw)
        posix = path.as_posix()
        name = path.name

        if name.startswith(".env") and name != ".env.example":
            problems.append(f"{posix}: environment file — secrets never belong in the repo")
            continue

        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{posix}: {path.suffix} is data or key material, not source")
            continue

        if any(part in posix for part in FORBIDDEN_NAME_PARTS):
            problems.append(f"{posix}: database dump")
            continue

        if not posix.startswith(SOURCE_PREFIXES) and posix.startswith(FORBIDDEN_DIRS):
            problems.append(f"{posix}: lives in a collected-data directory")
            continue

        if name in SIZE_ALLOWLIST:
            continue

        if path.is_file():
            size = path.stat().st_size
            if size > MAX_BYTES:
                problems.append(
                    f"{posix}: {size:,} bytes exceeds the {MAX_BYTES:,} limit — "
                    f"if this is data it does not belong here; if it is source, "
                    f"add it to SIZE_ALLOWLIST"
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Explicit paths to check")
    parser.add_argument("--all", action="store_true", help="Check every tracked file")
    args = parser.parse_args()

    if args.paths:
        paths = args.paths
    elif args.all:
        paths = tracked_files()
    else:
        paths = staged_files()

    if not paths:
        print("OK — nothing to check")
        return 0

    problems = check(paths)
    if problems:
        print("Refusing to allow these files:\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nThird-party payloads must not be redistributed and credentials must "
            "not be committed. If a file is legitimate source, adjust the rule "
            "deliberately rather than bypassing the check.",
            file=sys.stderr,
        )
        return 1

    print(f"OK — {len(paths)} file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
