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

**Prerequisite: Docker. That is the whole list.**

### Linux / macOS

```bash
git clone <repo> emeye && cd emeye
make up          # creates .env from the template, then stops so you can fill it in
# edit .env: EMEYE_POSTGRES_PASSWORD and EMEYE_USER_AGENT
make up          # builds and starts postgres + app
make migrate     # apply the schema
make psql        # \dt should list schema_meta and alembic_version
```

### Windows

**Run everything inside WSL2, not PowerShell or CMD.** `make` is a Unix tool
that Windows does not ship, and the Makefile drives a bash shell. WSL2 is also
the supported path because the container base is Ubuntu 24.04 — inside WSL2 the
host and the container are the same platform, so there is nothing to translate.

```powershell
wsl --install -d Ubuntu        # once, then reboot
```

Then enable **Settings → Resources → WSL Integration** for your distro in Docker
Desktop, open the Ubuntu terminal, and follow the Linux steps above.

Two things that matter:

- **Clone inside the WSL filesystem** (`~/emeye`), not under `/mnt/c/...`.
  Bind mounts across the Windows/WSL boundary are slow enough to be
  user-visible, and file ownership does not map cleanly.
- If `make` is missing in a fresh Ubuntu: `sudo apt install make`.

### Without `make`

Every target is a thin wrapper. If you would rather not install `make`, or want
to run from PowerShell against Docker Desktop directly:

| Instead of | Run |
|---|---|
| `make up` | `docker compose up -d --build` |
| `make migrate` | `docker compose run --rm app alembic upgrade head` |
| `make downgrade` | `docker compose run --rm app alembic downgrade -1` |
| `make psql` | `docker compose exec postgres psql -U emeye -d emeye` |
| `make down` | `docker compose down` |
| `make logs` | `docker compose logs -f` |
| `make shell` | `docker compose exec app bash` |

`.env` has no bootstrap step outside `make`, so create it yourself first —
PowerShell: `Copy-Item .env.example .env`, bash: `cp .env.example .env` — and
fill in `EMEYE_POSTGRES_PASSWORD` and `EMEYE_USER_AGENT` before starting.
Compose refuses to start without the password.

`make help` lists every target.

### Troubleshooting

| Symptom | Cause |
|---|---|
| `make : The term 'make' is not recognized` | PowerShell. Use WSL2, or the table above. |
| `exec /usr/local/bin/entrypoint.sh: no such file or directory` | CRLF line endings. `.gitattributes` prevents this; if you cloned before it existed, run `git rm --cached -r . && git reset --hard`. |
| `EMEYE_POSTGRES_PASSWORD must be set` | `.env` missing or the password still blank. |
| `permission denied` on `src/` | Container UID does not match yours. Set `EMEYE_UID`/`EMEYE_GID` in `.env` to `id -u`/`id -g`, then `make build`. |
| Postgres never becomes healthy | `make logs` — usually a stale volume from a different password. `make nuke` wipes it (destroys data). |

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
