# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail the build when a dependency's license is incompatible with AGPL-3.0-or-later.

An incompatible transitive dependency caught at add-time is a five-minute
problem. Caught two years later, it is a rewrite.

Usage:
    python scripts/check_licenses.py            # check the installed environment
    python scripts/check_licenses.py --report   # also write the inventory
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import Distribution, distributions
from pathlib import Path

PROJECT_LICENSE = "AGPL-3.0-or-later"

# Licenses whose terms permit inclusion in an AGPL-3.0-or-later work.
# Permissive licenses flow inward freely; LGPL and MPL are weak-copyleft and
# compatible; GPL-3.0/AGPL-3.0 are the same family.
ALLOWED: set[str] = {
    "AGPL-3.0",
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-3.0",
    "GPL-3.0-or-later",
    "HPND",
    "ISC",
    "LGPL-3.0",
    "LGPL-3.0-or-later",
    "MIT",
    "MPL-2.0",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
    "Zlib",
}

# Known-incompatible: GPL-2.0-only cannot be combined with AGPL-3.0 work.
DENIED: set[str] = {
    "GPL-2.0",
    "GPL-2.0-only",
    "SSPL-1.0",
    "BUSL-1.1",
    "Commons-Clause",
    "Elastic-2.0",
}

# Packages whose metadata is unparseable or misleading, resolved by reading the
# project's own LICENSE file. Every entry MUST carry a justification — an
# exception without a reason is not an exception, it is a silenced alarm.
EXCEPTIONS: dict[str, tuple[str, str]] = {
    "typing-extensions": ("PSF-2.0", "Ships under the PSF license; metadata reports a bare file path"),
    "typing_extensions": ("PSF-2.0", "Same package, underscore-normalized name"),
}

# Substrings mapped to canonical SPDX ids. Package metadata is famously
# inconsistent ("MIT", "MIT License", "License :: OSI Approved :: MIT License").
_NORMALIZE: list[tuple[str, str]] = [
    ("apache software license", "Apache-2.0"),
    ("apache 2.0", "Apache-2.0"),
    ("apache-2.0", "Apache-2.0"),
    ("apache license", "Apache-2.0"),
    ("bsd-3-clause", "BSD-3-Clause"),
    ("bsd-2-clause", "BSD-2-Clause"),
    ("bsd license", "BSD-3-Clause"),
    ("bsd", "BSD-3-Clause"),
    ("gnu affero", "AGPL-3.0-or-later"),
    ("agpl", "AGPL-3.0-or-later"),
    ("gnu lesser general public license v3", "LGPL-3.0"),
    ("lgpl-3", "LGPL-3.0"),
    ("lgpl", "LGPL-3.0"),
    ("gnu general public license v3", "GPL-3.0"),
    ("gpl-3", "GPL-3.0"),
    ("mozilla public license 2.0", "MPL-2.0"),
    ("mpl-2.0", "MPL-2.0"),
    ("mit license", "MIT"),
    ("mit", "MIT"),
    ("isc", "ISC"),
    ("python software foundation", "PSF-2.0"),
    ("psf", "PSF-2.0"),
    ("historical permission notice", "HPND"),
    ("unlicense", "Unlicense"),
    ("zlib", "Zlib"),
]


def normalize(raw: str) -> str | None:
    """Map messy license metadata onto a canonical SPDX id."""
    text = raw.strip().lower()
    if not text or text in {"unknown", "none"}:
        return None
    # A full license text dumped into the metadata field: too long to match.
    if len(text) > 200:
        text = text[:200]
    for needle, spdx in _NORMALIZE:
        if needle in text:
            return spdx
    return None


def license_of(dist: Distribution) -> tuple[str | None, str]:
    """Return (canonical SPDX id or None, raw source string)."""
    name = (dist.metadata["Name"] or "").strip()
    if name in EXCEPTIONS:
        return EXCEPTIONS[name][0], f"exception: {EXCEPTIONS[name][1]}"

    # Classifiers are more reliable than the free-text License field.
    classifiers = dist.metadata.get_all("Classifier") or []
    for classifier in classifiers:
        if classifier.startswith("License ::"):
            spdx = normalize(classifier.rsplit("::", 1)[-1])
            if spdx:
                return spdx, classifier

    expression = dist.metadata.get("License-Expression")
    if expression:
        spdx = normalize(expression)
        if spdx:
            return spdx, f"License-Expression: {expression}"

    raw = dist.metadata.get("License") or ""
    spdx = normalize(raw)
    if spdx:
        return spdx, f"License: {raw[:60]}"

    return None, raw[:60] or "(no license metadata)"


def collect() -> list[tuple[str, str, str | None, str]]:
    """Return (name, version, spdx, source) for every installed distribution."""
    rows = []
    for dist in distributions():
        name = (dist.metadata["Name"] or "?").strip()
        version = (dist.metadata["Version"] or "?").strip()
        spdx, source = license_of(dist)
        rows.append((name, version, spdx, source))
    return sorted(rows, key=lambda r: r[0].lower())


def write_report(rows: list[tuple[str, str, str | None, str]], path: Path) -> None:
    lines = [
        f"# Third-party licenses\n",
        f"\nProject license: **{PROJECT_LICENSE}**\n",
        "\nGenerated — do not edit by hand. Regenerate with:\n",
        "\n```bash\nuv run python scripts/check_licenses.py --report\n```\n",
        "\n| Package | Version | License | Source of the determination |\n",
        "|---|---|---|---|\n",
    ]
    for name, version, spdx, source in rows:
        lines.append(f"| `{name}` | {version} | {spdx or '**UNRESOLVED**'} | {source} |\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Write the inventory file")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/licenses/THIRD-PARTY.md"),
        help="Inventory output path",
    )
    args = parser.parse_args()

    rows = collect()
    if args.report:
        write_report(rows, args.out)
        print(f"wrote {args.out} ({len(rows)} distributions)")

    unresolved = [(n, v, s) for n, v, spdx, s in rows if spdx is None]
    denied = [(n, v, spdx) for n, v, spdx, _ in rows if spdx in DENIED]
    unknown = [
        (n, v, spdx) for n, v, spdx, _ in rows if spdx is not None and spdx not in ALLOWED
    ]

    failed = False
    if denied:
        failed = True
        print(f"\nDENIED — incompatible with {PROJECT_LICENSE}:", file=sys.stderr)
        for name, version, spdx in denied:
            print(f"  {name} {version}: {spdx}", file=sys.stderr)
    if unknown:
        failed = True
        print("\nNOT ON THE ALLOWLIST — review and add to ALLOWED or remove:", file=sys.stderr)
        for name, version, spdx in unknown:
            print(f"  {name} {version}: {spdx}", file=sys.stderr)
    if unresolved:
        failed = True
        print("\nUNRESOLVED — could not determine a license:", file=sys.stderr)
        for name, version, source in unresolved:
            print(f"  {name} {version}: {source}", file=sys.stderr)
        print(
            "\nResolve by reading the package's own LICENSE, then add an entry to "
            "EXCEPTIONS with a justification.",
            file=sys.stderr,
        )

    if failed:
        print(f"\nFAIL — see docs/LICENSING.md for the remediation path.", file=sys.stderr)
        return 1

    print(f"OK — {len(rows)} distributions, all compatible with {PROJECT_LICENSE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
