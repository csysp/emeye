# Plan 01-03 — Quality Gates & CI — Summary

**Completed:** 2026-08-21
**Status:** ✅ Host-verified · ⚠️ container path unverified (sandbox cannot pull images)

## What was built

| Artifact | Content |
|---|---|
| `pyproject.toml` | ruff (14 rule groups, line 100), mypy (strict-ish, per-module overrides), pytest (strict markers, `error::DeprecationWarning`), coverage |
| `tests/conftest.py` | Session-wide autouse socket block + isolated `settings` fixture |
| `tests/unit/` | 50 tests across config, CLI, engine, logging, repo scripts, network guard |
| `tests/integration/` | 5 migration tests, skip cleanly with no database |
| `scripts/check_no_payloads.py` | Secrets / payload / oversize guard |
| `.pre-commit-config.yaml` | ruff, detect-private-key, mixed-line-ending, plus the three local checks |
| `.github/workflows/ci.yml` | 5 jobs: lint, test, integration, compliance, build |
| `docker/Dockerfile` | New `builder-dev` + `dev` stages |
| `Makefile` / `make.ps1` | `test`, `test-integration`, `lint` given real bodies, at parity |

## Design decisions

**Tests run in a container, so Docker stays the only host requirement.** The
runtime image is built `--no-dev` and has no pytest, so a separate `dev` stage
adds the dev group. The deployed image never carries test or lint tooling.
`compose.override.yaml` builds `target: dev`; `compose.yaml` alone builds
`runtime`.

**CI invokes the Makefile targets** (REQ-29), not a parallel command list. The
one deliberate exception is the compliance job's repo-hygiene checks: they
inspect the git repository rather than the code, so they run on the runner with
stdlib Python, and pre-commit mirrors them locally. This is stated in the
workflow rather than left to be discovered.

**`EMEYE_WAIT_FOR_DB=0` on `test` and `lint`.** Both need the image, not the
database; without it the entrypoint would block for the full 60s timeout and
then fail.

## Verified on the host

| Check | Result |
|---|---|
| `ruff check .` | ✅ clean, 14 rule groups |
| `ruff format --check .` | ✅ 45 files |
| `mypy` | ✅ 12 source files |
| `pytest` | ✅ 50 passed, 5 skipped |
| `pytest -m unit` | ✅ 50 passed, network blocked |
| Integration suite with no database | ✅ skips with an actionable reason, does not error |
| `check_licenses.py` | ✅ exit 0 |
| `check_no_payloads.py --all` | ✅ exit 0 |
| Guard rejects `.env` / `.parquet` | ✅ exit 1 (verified by exit code, not output) |
| `check_task_parity.py` | ✅ 17 targets identical |
| YAML validity, all four files | ✅ |

The network guard is self-testing: `test_network_guard.py` asserts an outbound
connection raises and that loopback still works. If the block silently breaks,
those tests fail rather than everything continuing to pass while collectors
reach live services from CI.

## Defect found and fixed

**`configure_logging` was silently doing nothing whenever logging was already
configured.** `logging.basicConfig` is a documented no-op when the root logger
already has handlers — so under pytest, or any embedding host, or any library
that touches logging first, the app would have logged at the wrong level, to
the wrong stream, in the wrong format, with no error to show for it. Found
because the logging tests captured no output. Fixed with `force=True`.

This is the third defect in this phase that only surfaced by running the thing
rather than reading it.

## NOT verified

The container path — `make test`, `make lint`, and the `dev` image stage — has
never been executed. The sandbox cannot pull base images. Needs one run on the
owner's machine:

```powershell
.\make.ps1 lint
.\make.ps1 test
.\make.ps1 up; .\make.ps1 migrate; .\make.ps1 test-integration
```

The Python side is fully exercised on the host; what is untested is whether the
`dev` stage builds and whether the bind mounts line up inside the container.

## Carried forward

- CI has never run; the first push to a branch with the workflow will be its
  first execution.
- Coverage is measured but no threshold is enforced. A number is worth setting
  once there is real parsing code in phase 3 — enforcing one now would just be
  a ratchet on trivial code.
