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

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


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
    make_text = (SCRIPTS.parent / "Makefile").read_text(encoding="utf-8")
    ps_text = (SCRIPTS.parent / "make.ps1").read_text(encoding="utf-8")
    assert mod.makefile_targets(make_text) == mod.powershell_targets(ps_text)
