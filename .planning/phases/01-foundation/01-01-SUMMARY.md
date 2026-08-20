# Plan 01-01 — Python Project Skeleton — Summary

**Completed:** 2026-08-20
**Status:** ✅ Done

## What was built

| Artifact | Purpose |
|---|---|
| `pyproject.toml` + `uv.lock` | uv-managed project, `src/` layout, hatchling backend, `emeye` console script |
| `src/emeye/__init__.py` | Version read from package metadata, not duplicated |
| `src/emeye/config.py` | `Settings` (pydantic-settings, `EMEYE_` prefix) — the only reader of the environment |
| `src/emeye/logging.py` | structlog: console on a TTY, JSON when piped; idempotent |
| `src/emeye/cli/` | Typer app with all seven roadmap groups registered |
| `src/emeye/db/engine.py` | Lazy cached engine, `session_scope`, `check_connection` |

## Verification

| Check | Result |
|---|---|
| `uv sync` | ✅ 43 distributions resolved, lockfile committed |
| `emeye --help` lists all seven groups | ✅ ingest, enrich, dbt, forecast, export, status, backup |
| `emeye --version` | ✅ version + AGPL notice |
| Stub commands exit 2 | ✅ with a pointer to the delivering phase |
| `os.environ` / `os.getenv` outside `config.py` | ✅ zero matches (only a docstring mention) |
| `import emeye.db.engine` with no database | ✅ succeeds, no connection attempted |
| Missing required var | ✅ `ValidationError` naming `postgres_password` |
| All `enable_*` flags default False | ✅ all seven off |

## Findings

Two defects were caught during verification and fixed before commit:

1. **`database_url` as a `computed_field` leaked the plaintext password.**
   Pydantic includes computed fields in `repr()` and `model_dump()`, so any log
   line or diagnostic dump of the settings object would have carried the
   database password in clear text. `SecretStr` correctly masked the
   `postgres_password` field itself, which made the leak easy to miss — the
   masked field looked right while the derived URL beside it did not.
   Fixed by making `database_url` a plain `@property`, which is excluded from
   both. Verified: password absent from `repr()` and `model_dump()`, present in
   the URL where it belongs.

2. **Stub commands had no help text.** An f-string cannot be a docstring — it is
   evaluated as a no-op expression — so `f"""Placeholder for '{name}'."""`
   silently produced a `None` docstring and Typer rendered empty help. Fixed by
   passing `help=` to the command decorator explicitly.

Also of note:

- `NotImplementedYet` was refactored from a `typer.Exit` subclass that printed
  in its constructor into a plain function returning the exit. Side effects in
  an exception constructor are surprising to read and hard to test.
- `enable_spotify`, `spotify_client_id` and `spotify_client_secret` were added
  beyond the plan's list, following the owner's decision to make Spotify an
  active source.

## Deviations from plan

- Plan said to leave license metadata out of `pyproject.toml` so `01-04` could
  own it. Since `01-04` ran first in the same wave and the license was already
  decided, the metadata was written correctly on the first pass. The intent —
  never write a license value that might disagree with the decision — was
  honored.
