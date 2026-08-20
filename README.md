# emeye — Electronic Music Eye

A personal, local-first data warehouse and analysis toolkit for **electronic /
club music production trends**.

emeye ingests catalog and chart data from Beatport plus free open-music APIs
(MusicBrainz, Discogs, Deezer, Last.fm, ListenBrainz), normalizes it into a
PostgreSQL warehouse, and produces long-horizon trend analytics and forecasts
over tempo, key, song-title language, label dominance, and artist / remixer
activity.

Everything runs in Docker. Single user, no cloud, no accounts.

## Status

Pre-implementation. Planning artifacts live in [`.planning/`](.planning/);
architecture and conventions live in [`CLAUDE.md`](CLAUDE.md).

## Documentation

| Doc | What's in it |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project direction, stack, architecture, conventions, guardrails |
| [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) | Per-source access, fields, rate limits, legal posture |
| [`docs/DOMAIN.md`](docs/DOMAIN.md) | Genre taxonomy, key/Camelot handling, title & mix-name grammar |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data flow, layering, schema contracts |
| [`.planning/ROADMAP.md`](.planning/ROADMAP.md) | Phase breakdown |
| [`.planning/REQUIREMENTS.md`](.planning/REQUIREMENTS.md) | Numbered requirements |

## Quickstart

**Prerequisite: Docker. That is the whole list** — no WSL, no `make`, no Python
on the host.

The project is developed and tested on **Windows** and deployed to
**Ubuntu 24.04 LTS**. Both are first-class; the same commands work on each.

### Windows (PowerShell)

```powershell
git clone <repo> emeye; cd emeye
.\make.ps1 up          # creates .env from the template, then stops
notepad .env           # set EMEYE_POSTGRES_PASSWORD and EMEYE_USER_AGENT
.\make.ps1 up          # builds and starts postgres + app
.\make.ps1 migrate     # apply the schema
.\make.ps1 psql        # \dt lists schema_meta and alembic_version
```

If PowerShell refuses to run the script (`running scripts is disabled on this
system`), either allow local scripts once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

or bypass per-invocation: `powershell -ExecutionPolicy Bypass -File .\make.ps1 up`.

### Linux / macOS

```bash
git clone <repo> emeye && cd emeye
make up          # creates .env from the template, then stops
nano .env        # set EMEYE_POSTGRES_PASSWORD and EMEYE_USER_AGENT
make up && make migrate && make psql
```

`make help` / `.\make.ps1 help` lists every target. The two runners are kept at
target parity by `scripts/check_task_parity.py`, which fails CI on divergence.

### Deploying to Ubuntu 24.04 LTS

Development bind-mounts `src/` via `compose.override.yaml` so edits apply
without a rebuild. **Deployment must bypass that override** so the container
runs the image that was actually built and tested:

```bash
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml run --rm app alembic upgrade head
```

The `-f compose.yaml` is load-bearing. Without it Compose picks up the dev
override and the container runs whatever happens to be in the host's `src/`.

Set `EMEYE_UID` / `EMEYE_GID` in `.env` to match `id -u` / `id -g` on the
deployment host if it is not the usual 1000, then rebuild. (On Windows this has
no effect — Docker Desktop synthesizes ownership for bind mounts — which is why
it can be left alone during development.)

### Without a task runner

Both runners are thin wrappers. The raw equivalents:

| Target | Command |
|---|---|
| `up` | `docker compose up -d --build` |
| `migrate` | `docker compose run --rm app alembic upgrade head` |
| `downgrade` | `docker compose run --rm app alembic downgrade -1` |
| `psql` | `docker compose exec postgres psql -U emeye -d emeye` |
| `down` | `docker compose down` |
| `logs` | `docker compose logs -f` |
| `shell` | `docker compose exec app bash` |

Create `.env` yourself first (`Copy-Item .env.example .env` or
`cp .env.example .env`) — Compose refuses to start without the password.

### Troubleshooting

| Symptom | Cause |
|---|---|
| `make : The term 'make' is not recognized` | You are in PowerShell — use `.\make.ps1` instead. |
| `running scripts is disabled on this system` | PowerShell execution policy; see above. |
| `exec /usr/local/bin/entrypoint.sh: no such file or directory` | CRLF line endings. `.gitattributes` prevents this; if you cloned before it existed, `git rm --cached -r . && git reset --hard`. |
| `EMEYE_POSTGRES_PASSWORD must be set` | `.env` missing, or the password is still blank. |
| `permission denied` on `src/` (Linux only) | Container UID does not match yours. Set `EMEYE_UID`/`EMEYE_GID` in `.env`, then rebuild. |
| Postgres never becomes healthy | `logs` — usually a stale volume from a different password. `nuke` wipes it (destroys data). |

## Method

Development follows [GSD Core](https://github.com/open-gsd/gsd-core), cloned
into `gsd-core/` and deliberately left untracked. Refresh with
`git -C gsd-core pull`.

## License

**AGPL-3.0-or-later.** See [`LICENSE`](LICENSE) for the full text and
[`docs/LICENSING.md`](docs/LICENSING.md) for the reasoning and the dependency
compatibility policy.

In plain terms: you may use, modify and share emeye freely, but if you
distribute it — **or run a modified version as a network service** — you must
offer your users the complete source of your version under these same terms.

## Legal posture on collected data

A separate concern from the license above: that one governs emeye's own code,
this one governs how emeye treats other people's data.

Personal research use only. Collectors honor `robots.txt`, rate-limit to a
trickle, identify themselves honestly, and never evade bot protection. No
third-party data is redistributed from this repository.
