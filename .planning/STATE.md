---
gsd_state_version: '1.0'
status: executing
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 30
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-20)

**Core value:** A trustworthy, continuously-growing longitudinal dataset of the electronic music release landscape.
**Current focus:** Phase 1 — Foundation (planned, ready to execute)

## Current Position

Phase: 2 of 8 (Ingestion Framework)
Plan: 0 of 3 in current phase — planned, awaiting review
Status: Phase 2 planned. Awaiting owner review before execution.
Last activity: 2026-08-20 — Phase 1 planned; owner decisions recorded (license, Beatport posture, Spotify role, chart scope). `01-CONTEXT.md` captures 21 locked implementation decisions; four executable plans written across three waves. Licensing added to Phase 1 as plan 01-04 with a blocking decision checkpoint.

**Execution waves for Phase 2:**
- Wave 1 (parallel): `02-01` bronze schema + store · `02-02` polite HTTP layer
- Wave 2: `02-03` job contract, runner, CLI, scheduler, the guarantee tests

No checkpoints — all three plans are autonomous. Bronze storage was settled at
the discuss step (JSONB), so nothing blocks.

**Phase 2 decisions (owner, 2026-08-21):** JSONB payloads · synchronous httpx ·
cron-in-container scheduler · `ingest_run` with a `skipped_cache` status ·
robots.txt as a first-class fail-closed component.

**Execution waves for Phase 1 (complete):**
- Wave 1 (parallel): ✅ `01-01` Python project skeleton · ✅ `01-04` Licensing & governance
- Wave 2: ✅ `01-02` Container stack — built and verified end to end on Windows 2026-08-21
- Wave 3: ✅ `01-03` Quality gates and CI — 57 tests, 5 CI jobs, all green on GitHub Actions

The license checkpoint in `01-04` is **resolved** — AGPL-3.0-or-later. All four
plans are now autonomous.

All six open questions were answered 2026-08-20 (see PROJECT.md). Wave 1 is
executing.

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions
affecting current work:

- [Init]: Postgres as system of record, dbt-core for silver→gold, DuckDB for ad-hoc
- [Init]: Medallion layering with immutable bronze; parsing is replayable, never re-scraped
- [Init]: Chart ingestion (Phase 3) ships before analytics — chart history is irrecoverable
- [Init]: Beatport collector gated behind explicit opt-in; ToS prohibits automated collection
- [Init]: Spotify excluded as tempo/key source — audio-features deprecated for new apps
- [Init]: Typer CLI + cron container instead of an orchestrator; job graph is shallow
- [Owner, 2026-08-20]: **AGPL-3.0-or-later** — obligations are well-understood, unlike a bespoke source-available license
- [Owner, 2026-08-20]: No sanctioned Beatport API; minimal scraping on chart reset, detail fetches only for unseen track IDs
- [Owner, 2026-08-20]: Chart scope = Beatport Top 100 + Hype 100 + selected Spotify dance playlists; no per-genre sweep
- [Owner, 2026-08-20]: Beatport is the primary BPM origin but not the source of truth — cross-referenced, disagreement retained
- [Owner, 2026-08-20]: Spotify is a metadata + playlist-chart source via the official API; never tempo or key
- [Owner, 2026-08-20]: Genre taxonomy work dropped for v1 — charts-only scope makes the crosswalk unnecessary
- [Owner, 2026-08-20]: Spotify v1 tracks `mint` only; further playlists are additive later
- [Owner, 2026-08-20]: No personal library — no local audio analysis, no ground truth, Essentia/librosa out of the stack
- [Owner, 2026-08-20]: Bronze payloads kept indefinitely; no pruning or TTL
- [Owner, 2026-08-20]: Postgres backup is manual to a thumb drive — `emeye backup` makes the file, the human moves it
- [Phase 1 planning]: Source enable flags default to False, so merging a collector never starts collection
- [Phase 1 planning]: Tests run with outbound networking blocked at the socket layer, not by convention

### Pending Todos

None yet.

### Blockers/Concerns

- **Beatport access route is unresolved.** Phase 3 opens with a spike (03-01) to
  determine whether sanctioned API access is obtainable. Everything downstream
  assumes some viable route exists; if none does, scope shifts toward
  Deezer/MusicBrainz/Discogs and the tempo+key coverage story gets materially weaker.
- **Time-to-value is long by nature.** Meaningful trend and forecast output needs
  12–24 months of self-collected chart history. Catalog backfill via release
  dates partially offsets this; expectations should be set accordingly.
- **Collection is a slow burn.** The dataset needs 6–12 months of accumulation
  before it answers anything interesting. Nothing downstream should be optimized
  for speed of first result; the job is to start collecting and keep collecting.
- **Spotify editorial-playlist access is an unverified assumption.** The Nov 2024
  API changes restricted Spotify-owned editorial playlists (`mint` among them)
  for new apps. Plan `04-04` must verify against a real app registration before
  any playlist design is committed. Fallbacks are documented in DATA-SOURCES.md.
- **No ground-truth BPM/key corpus exists.** With no personal library, vendor
  values can never be audited against reality. Cross-source disagreement
  (Beatport vs Deezer) is the only quality signal we will ever have — so
  retaining disagreement instead of averaging it is load-bearing. Essentia and
  librosa drop out of the stack entirely, which also removes one of the two
  original arguments for AGPL; the network-deployment argument still stands on
  its own and the decision is unchanged.
- **`mint` is a single point of failure for the Spotify chart signal.** With
  only one playlist tracked, if editorial-playlist access turns out to be
  unavailable to a new app, there is no Spotify chart signal at all — not a
  degraded one. `04-04` must verify access *before* building the connector, not
  after.
- **Bronze grows forever by decision.** At the designed trickle (~2 chart docs
  plus a handful of detail docs per day) this is single-digit GB over a decade,
  so it is comfortably affordable — but nothing may quietly raise that rate
  without revisiting the choice.
- **Backups are manual and therefore forgettable.** `emeye status` must surface
  days-since-last-backup so the gap is visible before it matters.

## Deferred Items

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Sources | Traxsource / Juno collectors | Deferred | Init | v1.1 |
| Sources | Resident Advisor event data | Deferred | Init | v1.1 |
| Validation | Local audio analysis (Essentia/librosa) ground truth | Deferred | Init | v1.1 |
| Analytics | Remix-network graph analysis | Deferred | Init | v1.1 |
| Tooling | Metabase container | Deferred | Init | v1.1 |
| Backfill | Internet Archive historical chart recovery | Deferred | Init | v1.1 |

## Session Continuity

Last session: 2026-08-20 — Phase 1 planning complete.
Next step: owner reviews the three Phase 2 plans, then execute wave 1
(`02-01` and `02-02` in parallel).

**Wave 3 landed.** `check_licenses`, `check_no_payloads` and `check_task_parity`
are all wired into CI. `make test` / `test-integration` / `lint` have real
bodies and run inside a new `dev` image stage, so Docker remains the only host
requirement. 50 unit tests + 5 integration tests; the network guard self-tests.

⚠️ **Owner action required before Phase 1 closes.** The container image has
never been built — this sandbox's network policy blocks Docker Hub layer
downloads (403), so `ubuntu:24.04` and `postgres:16` could not be pulled. Run on
the Ubuntu machine:

```bash
make up && make migrate && make psql    # then \dt
make downgrade && make migrate          # round-trip
make down && make up                    # persistence
```

Most likely failure points, both loud rather than subtle: the `userdel -r
ubuntu` step that frees UID 1000, and named-volume ownership for `/data`.

**Platform posture (settled 2026-08-20):** the owner develops and tests on
**Windows** and deploys to **Ubuntu 24.04 LTS**. Both are first-class.

- `make.ps1` gives Windows the same 17 targets as the Makefile, with Docker
  Desktop as the only prerequisite — no WSL, no make, no host Python. The
  interim "Windows via WSL2" guidance is **withdrawn**.
- `scripts/check_task_parity.py` fails the build when the two runners diverge,
  including a target handled but missing from help. Two runners is the price of
  native support on both platforms; the check is what stops that price turning
  into a silent bug where a target works on one platform only.
- compose is split: `compose.yaml` is the **deployment** definition and runs the
  built image; `compose.override.yaml` is auto-applied for development and
  bind-mounts `src/`. Deployment **must** pass `-f compose.yaml`, or the
  container runs host source instead of the image that was tested.
- `.gitattributes` forces LF (now including `*.ps1`). Git for Windows defaults
  to autocrlf=true, and a CRLF `entrypoint.sh` fails in-container with a
  misleading "no such file or directory".
- Note the UID asymmetry: `EMEYE_UID`/`EMEYE_GID` matter on the Ubuntu
  deployment host but are inert on Windows, where Docker Desktop synthesizes
  ownership for bind mounts. A permissions problem will therefore appear at
  deployment, not during development.
