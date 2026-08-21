# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI surface."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from emeye.cli.groups import GROUPS
from emeye.cli.main import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture(autouse=True)
def _required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMEYE_POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("EMEYE_USER_AGENT", "emeye-test/0.0 (+mailto:t@example.invalid)")


def test_help_lists_every_group() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in GROUPS:
        assert group in result.output


def test_version_reports_version_and_license() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "emeye" in result.output
    assert "AGPL" in result.output


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_stub_exits_two_not_zero(group: str) -> None:
    """A stub that exits 0 is the dangerous case: a scheduler reads it as done."""
    result = runner.invoke(app, [group, "run"])
    assert result.exit_code == 2


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_stub_names_its_delivering_phase(group: str) -> None:
    result = runner.invoke(app, [group, "run"])
    assert str(GROUPS[group][1]) in result.output
