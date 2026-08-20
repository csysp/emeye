# Plan 01-02 — Container Stack — Summary

**Completed:** 2026-08-20
**Status:** ⚠️ Built and statically verified; **runtime verification blocked by the environment**

## Refactor from plan

Owner requested Ubuntu build compatibility. Base image changed from
`python:3.12-slim` to **`ubuntu:24.04`**, recorded as D-04a in `01-CONTEXT.md`.

Ubuntu 24.04 LTS carries CPython 3.12 in its main archive, so the container
shares interpreter build, glibc and OpenSSL with an Ubuntu host. Three
consequences were handled rather than discovered later:

1. **`UV_PYTHON_PREFERENCE=only-system`** — without it uv downloads its own
   managed CPython, which would silently defeat the entire point of the base.
2. **UID 1000 collision** — Ubuntu 24.04 ships a built-in `ubuntu` account
   already holding UID 1000. It is removed so the app user can take 1000 and
   match a standard single-user desktop, keeping bind mounts writable with no
   host-side chown. Overridable via `EMEYE_UID`/`EMEYE_GID`.
3. **Main archive only** — no universe packages. This is why PID-1 handling
   comes from compose `init: true` rather than a `tini` package.

## What was built

| Artifact | Notes |
|---|---|
| `docker/Dockerfile` | Two stages, deps layer before source, non-root runtime, `/data` chowned so a fresh named volume inherits ownership |
| `docker/entrypoint.sh` | Bounded wait for postgres with an actionable timeout message |
| `compose.yaml` | postgres 16 + app, healthcheck gating, loopback-only ports, named volumes |
| `.env.example` | Every setting in `config.py`, grouped, with required values called out |
| `alembic.ini` + `db/alembic/` | URL from `emeye.config`, never from the ini |
| `db/base.py`, `db/models.py` | Declarative base + `schema_meta` |
| `versions/0001_initial.py` | Creates `schema_meta`, seeds `schema_initialized_at`, working downgrade |
| `Makefile` | 17 targets, all through compose |

Two design choices worth noting beyond the plan:

- **`POSTGRES_INITDB_ARGS: --locale=C`.** Left to the host locale, index
  ordering differs between machines and a dump restored elsewhere may not match
  its source. For a warehouse whose backup story is a thumb drive moving between
  machines, deterministic collation matters.
- **`make nuke`** requires typing `nuke` to confirm. `make clean` deliberately
  keeps the database volume — the data is the irreplaceable asset.

## Verified

| Check | Result |
|---|---|
| `docker compose config` | ✅ valid |
| Missing `.env` halts `make up` with instructions | ✅ exits 1, names the two required values |
| `make help` self-documents | ✅ 17 targets |
| Alembic sees revision `0001` | ✅ `<base> -> 0001 (head)` |
| Offline `upgrade head --sql` | ✅ correct DDL for `alembic_version` + `schema_meta` + seed row |
| Offline `downgrade --sql` | ✅ `DROP TABLE schema_meta` |
| ORM metadata matches the migration | ✅ same columns and PK, so autogenerate will not emit a spurious diff |
| `env.py` reads settings, not `alembic.ini` | ✅ proven — offline SQL generation required no ini URL |
| `alembic.ini` contains no credentials | ✅ `sqlalchemy.url` absent |
| `bash -n docker/entrypoint.sh` | ✅ valid |
| No Makefile target uses host python/uv/alembic/psql | ✅ all via `docker compose` |

## NOT verified — environment limitation

**The image was never built and the stack was never run.** This sandbox's
network policy returns HTTP 403 for Docker Hub layer downloads
(`production.cloudfront.docker.com`), so `ubuntu:24.04` and `postgres:16` cannot
be pulled. A Docker daemon was started successfully; the block is on registry
egress, not on Docker.

Consequently these plan criteria remain **unproven**:

- The image builds
- `make up` yields a healthy postgres and a running app
- `make migrate` applies `0001` against a live database
- upgrade → downgrade → re-upgrade round-trips
- Data survives `make down` && `make up`
- `make psql` connects and `\dt` shows the tables
- The fresh-clone portability walkthrough (plan Task 5)

The static checks above cover the wiring — the migration SQL, the settings
integration, the compose topology and the Makefile are all confirmed correct.
What is untested is the **image build itself**: apt package availability, the
uv binary path in the `ghcr.io/astral-sh/uv` image, the `userdel -r ubuntu`
step, and volume ownership behavior.

**These must be run on the owner's Ubuntu machine before Phase 1 is closed:**

```bash
make up && make migrate && make psql   # then \dt
make downgrade && make migrate         # round-trip
make down && make up && make psql      # persistence
```

Risk assessment: moderate. The Dockerfile deliberately uses only well-trodden
constructs and was simplified during this plan to shrink the untested surface —
apt cache mounts and the `tini` package were both removed in favour of plainer
alternatives. The most likely failure points are the `userdel` step and volume
ownership, both of which fail loudly and visibly rather than subtly.

## Defect found and fixed

Running the config against a real `.env.example` surfaced a startup bug that
would have hit on the **first `make up`**: `EMEYE_LOG_JSON=` with a blank value
fails `bool | None` parsing outright, so the app would not have started at all.
`.env.example` shipped exactly that line.

Fixed generally rather than for the one field: blank values for optional
settings now coerce to `None`. This also closes a latent bug for Phase 4 — an
unset `EMEYE_DISCOGS_TOKEN=` was becoming `SecretStr("")`, which is **truthy**,
so a credential presence check would have read an unset token as configured.

## Carried forward

- `make test`, `make test-integration` and `make lint` are stubs that exit 2.
  Plan `01-03` gives them real bodies.
- The fresh-clone portability walkthrough (plan Task 5) is deferred to the
  owner's machine; README Quickstart should be written after it actually runs.
