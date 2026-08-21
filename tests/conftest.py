# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared fixtures.

The important one is :func:`block_network`. CLAUDE.md forbids tests from
touching live upstream services, and a rule that is only written down gets
broken. Blocking the socket layer makes the rule structural: a test that
tries to reach Beatport fails loudly instead of quietly succeeding — and
succeeding is the dangerous outcome, because it means we shipped a collector
that ran against production during CI.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import pytest

from emeye.config import Settings

_REAL_CONNECT = socket.socket.connect
_REAL_CREATE_CONNECTION = socket.create_connection

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", ""}


class NetworkBlockedError(RuntimeError):
    """Raised when a test attempts an outbound connection."""


def _is_allowed(address: Any) -> bool:
    """Loopback and the compose database stay reachable for integration tests."""
    if isinstance(address, tuple) and address:
        return str(address[0]) in _ALLOWED_HOSTS
    # AF_UNIX and anything else non-inet: not an outbound network call.
    return True


@pytest.fixture(autouse=True, scope="session")
def block_network() -> Iterator[None]:
    """Block outbound sockets for the entire session."""

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if not _is_allowed(address):
            raise NetworkBlockedError(
                f"outbound network call to {address!r} blocked. Tests must use "
                f"recorded fixtures (respx), never a live service."
            )
        return _REAL_CONNECT(self, address)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_allowed(address):
            raise NetworkBlockedError(
                f"outbound network call to {address!r} blocked. Tests must use "
                f"recorded fixtures (respx), never a live service."
            )
        return _REAL_CREATE_CONNECTION(address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = _REAL_CONNECT  # type: ignore[method-assign]
        socket.create_connection = _REAL_CREATE_CONNECTION  # type: ignore[assignment]


@pytest.fixture
def settings() -> Settings:
    """A fully-populated Settings built from explicit test values.

    Never reads the developer's .env — a test whose result depends on local
    configuration is not a test.
    """
    return Settings(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="emeye_test",
        postgres_user="emeye_test",
        postgres_password="test-password",  # noqa: S106 - fixture value, not a credential
        user_agent="emeye-test/0.0 (+mailto:test@example.invalid)",
    )
