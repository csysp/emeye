# SPDX-License-Identifier: AGPL-3.0-or-later
"""The guard that guards the guard.

If the network block silently stops working, every other test keeps passing
and nobody notices until a collector hits a live service from CI. These tests
fail the moment the block is broken.
"""

from __future__ import annotations

import socket

import pytest

from tests.conftest import NetworkBlockedError

pytestmark = pytest.mark.unit


def test_outbound_connection_is_blocked() -> None:
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("api.beatport.com", 443), timeout=1)


def test_outbound_socket_connect_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlockedError):
            sock.connect(("1.1.1.1", 443))
    finally:
        sock.close()


def test_loopback_is_still_allowed() -> None:
    """Integration tests need the compose database; only outbound is blocked."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        server.close()
