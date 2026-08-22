# SPDX-License-Identifier: AGPL-3.0-or-later
"""REQ-02: reparse rebuilds from bronze alone.

Proving reparse merely does not *need* the network is weaker than proving it
*cannot use* it. The second is what makes bronze genuinely authoritative — and
what makes a wrong parser a cheap mistake instead of lost data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

import emeye.http.client as client_module
from emeye.bronze import store_document
from emeye.cli.main import app
from emeye.config import get_settings
from emeye.db.engine import check_connection, get_engine

pytestmark = [pytest.mark.integration]

runner = CliRunner()


@pytest.fixture(scope="module", autouse=True)
def _require_database() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    if not check_connection():
        pytest.skip("no PostgreSQL reachable — start it with `make up`", allow_module_level=True)


@pytest.fixture(autouse=True)
def _seeded_bronze() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("alter table raw_document disable trigger raw_document_append_only"))
        conn.execute(text("delete from raw_document where source = 'demo'"))
        conn.execute(text("alter table raw_document enable trigger raw_document_append_only"))

    for index in range(3):
        store_document(
            source="demo",
            endpoint="charts/top100",
            url=f"https://example.invalid/charts/top100?page={index}",
            http_status=200,
            body=f'{{"page": {index}}}'.encode(),
            params={"page": index},
            payload={"page": index},
        )


def test_reparse_reads_every_bronze_document() -> None:
    result = runner.invoke(app, ["ingest", "reparse", "demo"])
    assert result.exit_code == 0
    assert "3" in result.output


def test_reparse_cannot_construct_an_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The strong form of the guarantee.

    Any attempt to build a client during reparse fails the test outright,
    rather than silently succeeding because nothing happened to call out.
    """

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reparse must not construct an HTTP client")

    monkeypatch.setattr(client_module.PoliteClient, "__init__", explode)

    result = runner.invoke(app, ["ingest", "reparse", "demo"])
    assert result.exit_code == 0, result.output


def test_reparse_of_an_unknown_source_is_not_an_error() -> None:
    result = runner.invoke(app, ["ingest", "reparse", "never-collected"])
    assert result.exit_code == 0
    assert "nothing in bronze" in result.output
