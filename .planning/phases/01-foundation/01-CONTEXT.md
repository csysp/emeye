# Phase 1: Foundation - Context

**Gathered:** 2026-08-20
**Status:** Ready for planning

<domain>
## Phase Boundary

A cloned repo becomes a running, empty warehouse with one command, under a
license that protects the work, with the quality gates that keep it honest in
place from commit one.

**In scope:** Python project skeleton, container stack, Postgres service,
Alembic wiring, CLI entrypoint, config, logging, lint/type/test tooling, CI,
license selection and application.

**Out of scope:** Any collector, any schema beyond the migration harness, any
analytics. No table other than what Alembic itself needs — bronze schema is
Phase 2's job.

</domain>

<decisions>
## Implementation Decisions

### Runtime and packaging
- **D-01:** Python 3.12, `uv` for dependency management, lockfile committed.
- **D-02:** `src/` layout, package name `emeye`, single console entrypoint `emeye`.
- **D-03:** One Docker image serves app, scheduler, Streamlit and Jupyter; only
  the command differs. Keeps build time and drift down.
- **D-04:** Multi-stage Dockerfile: builder installs into a venv via `uv sync
  --frozen`, runtime stage copies the venv. Non-root user in the runtime stage.
- **D-04a (amended 2026-08-20, owner):** Base image is **`ubuntu:24.04`**, not
  `python:3.12-slim`. Ubuntu 24.04 LTS ships CPython 3.12 in its main archive,
  so the container runs the same interpreter build, glibc and OpenSSL as an
  Ubuntu host — removing the "works in the container, not on the box" class of
  problem that a Debian-slim or Alpine base can introduce.
  Consequences that must be honored:
  - `UV_PYTHON_PREFERENCE=only-system` is mandatory. Left to itself uv will
    download its own managed CPython, silently defeating the entire point.
  - Ubuntu 24.04 ships a built-in `ubuntu` account already holding UID 1000.
    It is deleted so the app user can take UID 1000 and match a standard
    single-user Linux desktop, keeping bind mounts writable with no host chown.
  - The image depends only on Ubuntu's **main** archive. No package from
    universe (this is why PID-1 handling uses compose `init: true` rather than
    a `tini` package).

### Configuration
- **D-05:** `pydantic-settings` is the single source of env truth. Nothing else
  reads `os.environ`.
- **D-06:** Every variable documented in `.env.example`; `.env` is gitignored.
  Config must fail loudly at startup on a missing required value, not at first use.
- **D-07:** Per-source enable flags live in config and default to **off**, so a
  collector cannot start collecting simply because it was merged.

### Database and migrations
- **D-08:** PostgreSQL 16 in Compose with a named volume. No host Postgres.
- **D-09:** Alembic from day one, wired to the same settings object. `make
  migrate` runs `alembic upgrade head` inside the app container.
- **D-10:** Phase 1 ships the migration harness plus one trivial revision to
  prove the loop end to end; real tables arrive in Phase 2.

### CLI and logging
- **D-11:** Typer with command groups matching the roadmap's verbs: `ingest`,
  `enrich`, `dbt`, `forecast`, `export`, `status`, `backup`. Phase 1 registers
  the groups with stubs so the surface is visible and testable early.
- **D-12:** Structured key/value logging to stdout (`structlog`), human-readable
  in a TTY and JSON otherwise. No log files — the container runtime owns that.
- **D-13:** No network calls at import time. Ever. Enforced by a test.

### Quality gates
- **D-14:** `ruff` for both lint and format, line length 100. `mypy` on `src/`.
- **D-15:** `pytest` with networking disabled by default in the test session, so
  an accidental live call fails loudly rather than passing quietly.
- **D-16:** CI runs the identical commands `make lint` / `make test` run, so a
  green local run means a green CI run.
- **D-17:** CI additionally checks: no secrets, no third-party payload files, and
  dependency licenses compatible with the project license.

### Licensing
- **D-18:** The project takes a **strong protective (copyleft) license**, chosen
  deliberately at a blocking checkpoint rather than defaulted.
- **D-19:** Recommendation is **AGPL-3.0-or-later**. Reasoning: the Streamlit
  surface makes this network-deployable, so plain GPL-3.0 leaves the SaaS
  loophole open; AGPL closes it. It is also the only mainstream strong-copyleft
  choice that keeps **Essentia (AGPL-3.0)** usable for the deferred audio
  ground-truth work, and it stays compatible with the MIT/BSD/Apache-2.0
  dependency stack this project uses.
- **D-20:** The license decision is applied in **one pass across every surface**
  — `LICENSE`, `pyproject.toml` metadata and classifiers, `README.md`, source
  file headers — so no artifact ever disagrees with another about the terms.
- **D-21:** A dependency license inventory is generated and enforced in CI, so
  an incompatible transitive dependency is caught at the moment it is added,
  not years later.

### Claude's Discretion
- Exact Makefile target names beyond the documented set.
- Dockerfile layer ordering and cache strategy.
- Logging field names and the structlog processor chain.
- Whether the trivial Phase 1 migration creates a `schema_meta` table or uses a
  no-op revision.

</decisions>

<specifics>
## Specific Ideas

- `make up` must be the entire setup story on a fresh machine with only Docker
  installed. If a contributor needs anything else, that is a bug in the Makefile.
- The CLI surface should read like the roadmap: someone running `emeye --help`
  on day one should be able to see where the project is going.
- Licensing is a governance decision, not paperwork — it earns a blocking
  checkpoint because it is genuinely one-way. Relicensing later requires the
  consent of every contributor, and any code someone else took under the old
  terms stays under them.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project direction
- `CLAUDE.md` — stack table, repo layout, code conventions, agent working agreements
- `.planning/PROJECT.md` — core value, scope boundaries, key decisions
- `.planning/REQUIREMENTS.md` — REQ-01, REQ-24, REQ-25, REQ-27, REQ-29, REQ-30, REQ-31

### Architecture
- `docs/ARCHITECTURE.md` — container topology, layer contracts, operational concerns

### Domain (not needed in Phase 1, required from Phase 3 on)
- `docs/DOMAIN.md` — key/tempo/title/genre invariants
- `docs/DATA-SOURCES.md` — per-source access and legal posture

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
None — greenfield. `gsd-core/` is vendored reference material and is untracked;
it is never imported or built.

### Established Patterns
Conventions are declared in `CLAUDE.md` before any code exists. Phase 1's job is
to make those conventions executable (lint config, type config, test config)
rather than aspirational.

### Integration Points
- `src/emeye/config.py` is the seam every later phase depends on — collectors,
  dbt invocation and the Streamlit app all read settings from it.
- `src/emeye/db/` engine/session factory is the seam for Phase 2's bronze schema.
- The CLI group registry is where every later phase attaches its commands.

</code_context>

<deferred>
## Deferred Ideas

- Streamlit, Jupyter and Metabase services in Compose — the image supports them;
  the services land in Phase 8 when there is something to look at.
- Scheduler container — defined in Phase 2 alongside the job runner it invokes.
- `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` — single-user project; revisit only if
  the repo is ever opened to outside contributors.
- Contributor License Agreement / DCO — only relevant if outside contributions
  arrive; noted because it interacts with any future relicensing.

</deferred>
