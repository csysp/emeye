# SPDX-License-Identifier: AGPL-3.0-or-later
"""The repo-hygiene scripts themselves.

A check that cannot fail is not a check, so each of these proves both the
pass and the fail path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _read_runner(name: str) -> str:
    """Read a task runner, failing with the actual cause if it is not mounted.

    Inside the dev container these arrive via compose.override.yaml. A bare
    FileNotFoundError here reads as a broken test rather than a missing mount,
    so say which it is.
    """
    path = REPO / name
    if not path.is_file():
        pytest.fail(
            f"{name} not found at {path}. Inside the container it is provided by "
            f"a read-only mount in compose.override.yaml — check that mount rather "
            f"than this test."
        )
    return path.read_text(encoding="utf-8")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_license_allowlist_accepts_current_stack() -> None:
    mod = _load("check_licenses")
    for spdx in ("MIT", "Apache-2.0", "BSD-3-Clause", "LGPL-3.0", "MPL-2.0", "ISC"):
        assert spdx in mod.ALLOWED


def test_license_denylist_blocks_incompatible() -> None:
    mod = _load("check_licenses")
    for spdx in ("GPL-2.0", "SSPL-1.0", "BUSL-1.1"):
        assert spdx in mod.DENIED
        assert spdx not in mod.ALLOWED


def test_license_normalizer_handles_messy_metadata() -> None:
    """Packages report licenses inconsistently; the normalizer is the fix."""
    mod = _load("check_licenses")
    assert mod.normalize("MIT License") == "MIT"
    assert mod.normalize("Apache Software License") == "Apache-2.0"
    assert mod.normalize("GNU Lesser General Public License v3") == "LGPL-3.0"
    assert mod.normalize("") is None
    assert mod.normalize("UNKNOWN") is None


def test_every_license_exception_carries_a_justification() -> None:
    """An exception without a reason is a silenced alarm, not an exception."""
    mod = _load("check_licenses")
    for package, (spdx, reason) in mod.EXCEPTIONS.items():
        assert spdx, package
        assert reason and len(reason) > 10, f"{package} has no real justification"


def test_task_parity_detects_divergence() -> None:
    mod = _load("check_task_parity")
    makefile = ".PHONY: up down\nup:\n\t@echo\ndown:\n\t@echo\n"
    assert mod.makefile_targets(makefile) == {"up", "down"}

    ps = """
switch ($Target.ToLower()) {
    'up' { }
    default { }
}
"""
    assert mod.powershell_targets(ps) == {"up"}


def test_task_parity_holds_for_the_real_runners() -> None:
    mod = _load("check_task_parity")
    make_text = _read_runner("Makefile")
    ps_text = _read_runner("make.ps1")
    assert mod.makefile_targets(make_text) == mod.powershell_targets(ps_text)


def test_powershell_helpers_are_called_with_arrays() -> None:
    """Guard against PowerShell parameter binding eating docker flags.

    PowerShell binds parameters before a function body runs, so a bare `-e` in
    `Invoke-Compose run --rm -e VAR=1 app` is parsed as a PowerShell parameter
    name and fails as ambiguous with -ErrorAction/-ErrorVariable. Passing an
    explicit @( ... ) array makes the arguments data rather than syntax.

    This cannot be caught by running the script here — there is no pwsh in CI —
    so it is enforced structurally instead.
    """
    import re

    text = _read_runner("make.ps1")
    offenders: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("function "):
            continue
        match = re.search(r"\bInvoke-(?:Compose|App|AppNoDb)\s+(\S)", stripped)
        if match and match.group(1) not in {"@", "("}:
            offenders.append(stripped)

    assert not offenders, "helper called with loose tokens instead of an array:\n" + "\n".join(
        offenders
    )


def test_powershell_does_not_shadow_the_args_automatic_variable() -> None:
    """$Args is an automatic variable; a param named $Args is a latent bug."""
    text = _read_runner("make.ps1")
    assert "[string[]]$Args" not in text
