# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bronze hashing and store API, without a database."""

from __future__ import annotations

import hashlib

import pytest

from emeye.bronze import canonical_params_hash, content_hash

pytestmark = pytest.mark.unit


def test_params_hash_is_key_order_independent() -> None:
    assert canonical_params_hash({"a": 1, "b": 2}) == canonical_params_hash({"b": 2, "a": 1})


def test_params_hash_distinguishes_different_params() -> None:
    assert canonical_params_hash({"page": 1}) != canonical_params_hash({"page": 2})


def test_params_hash_handles_none_and_empty_identically() -> None:
    assert canonical_params_hash(None) == canonical_params_hash({})


def test_params_hash_is_stable_across_runs() -> None:
    """Hard-coded so a change to the canonicalisation is a visible failure.

    If this value changes, every existing bronze row's params_hash stops
    matching newly computed ones, and cache lookups silently miss.
    """
    assert canonical_params_hash({"chart": "top100", "page": 1}) == (
        hashlib.sha256(b'{"chart":"top100","page":1}').hexdigest()
    )


def test_content_hash_matches_sha256() -> None:
    body = b"the quick brown fox"
    assert content_hash(body) == hashlib.sha256(body).hexdigest()


def test_content_hash_differs_for_different_bytes() -> None:
    assert content_hash(b"a") != content_hash(b"b")


def test_store_exposes_no_mutation_helpers() -> None:
    """Bronze is append-only. There must be nothing to call by accident."""
    import emeye.bronze.store as store

    exported = {name for name in dir(store) if not name.startswith("_")}
    for forbidden in ("update_document", "delete_document", "purge", "prune"):
        assert forbidden not in exported
