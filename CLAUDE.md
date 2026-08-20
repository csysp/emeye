# CLAUDE.md — emeye (Electronic Music Eye)

Guidance for Claude Code (and any other agent) working in this repository.
Read this file first, then `.planning/STATE.md` for where the project currently is.

---

## Project

**emeye** is a personal, self-hosted data warehouse and analysis toolkit for
electronic / club music production trends. It ingests catalog and chart data
from Beatport plus free open-music APIs, normalizes it into a SQL warehouse,
and produces long-horizon trend analytics and forecasts over:

- **Tempo** — BPM distributions, drift, and multi-modality per genre/label/scene
- **Key / harmony** — musical key distribution, minor-vs-major share, Camelot clustering
- **Titles** — token/n-gram trends, mix-name grammar ("Extended Mix", "VIP", "Dub"…)
- **Labels** — release volume, chart share, market concentration, roster churn
- **Artists & remixers** — output cadence, debut/attrition rates, remix networks

**Core value:** a trustworthy, continuously-growing longitudinal dataset of the
electronic music release landscape. Every other feature (charts, models,
dashboards) is replaceable; the historical data is not.

**Audience:** one person (the repo owner). Personal analysis, local-first.

### Non-goals

Do not build these unless the owner explicitly asks:

- Multi-user support, authentication, RBAC, or tenancy
- Cloud deployment, managed services, or horizontal scaling
- A public API or any redistribution of third-party data
- Audio playback, DJ tooling, or library management
- Real-time / streaming ingestion (batch is sufficient and always will be)
- Anti-bot evasion, CAPTCHA solving, proxy rotation, or credential sharing

---

## Prime directive: start collecting now

Chart data is **not retroactively obtainable**. Beatport Top 100s, Hype charts,
and "new releases" ordering are snapshots — if we do not capture today's, today
is lost forever. Catalog metadata (release date, BPM, key, label) *is* mostly
backfillable, because it is attached to the release row.

Consequence for planning: the **daily snapshot job ships before the analytics
layer**. A phase that improves analysis but delays ingestion is mis-ordered.

---

## Technology stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | Type hints everywhere; `from __future__ import annotations` |
| Package/env | `uv` | `uv sync`, `uv run`; lockfile committed |
| CLI | Typer + Rich | Single entrypoint: `emeye <group> <command>` |
| HTTP | `httpx` + `tenacity` + `limits` | Async where it pays; polite by default |
| Parsing | `selectolax` / `lxml` | HTML only when no API exists |
| DB (system of record) | PostgreSQL 16 | Docker container, persistent volume |
| ORM / access | SQLAlchemy 2.0 Core (+ ORM for dimensions) | Prefer explicit SQL for analytics |
| Migrations | Alembic | Every schema change is a migration; no manual DDL |
| Transformations | dbt-core + `dbt-postgres` | Silver/gold layers are SQL models, tested |
| Analysis | Polars (primary), pandas (interop), DuckDB | DuckDB reads Parquet exports for ad-hoc work |
| Forecasting | statsmodels, scikit-learn, optionally `statsforecast` | Baselines before anything fancy |
| Viz / app | Plotly + Streamlit | Optional Metabase container for SQL browsing |
| Notebooks | Jupyter (in-container) | Notebooks are scratch; findings graduate into dbt/metrics code |
| Orchestration | Typer CLI invoked by cron in a scheduler container | Escalate to Dagster only if DAG complexity demands it |
| Quality | ruff (lint+format), mypy, pytest, pre-commit | CI runs the same commands as local |
| HTTP tests | `respx` + recorded fixtures | Never hit live services in tests |
| Runtime | Docker + Docker Compose | System-agnostic; `make up` is the only setup step |

**Stack rules**

- Anything that must run on the owner's machine runs in Compose. No host-level
  installs beyond Docker and (optionally) `uv` for editor tooling.
- No cloud SDKs, no paid services, no telemetry.
- Prefer boring, well-documented libraries; a dependency needs a reason.

---

## Repository layout

```
emeye/
├── CLAUDE.md                 # this file
├── README.md
├── Makefile                  # up, down, ingest, dbt, test, lint, shell, psql
├── compose.yaml              # postgres, app, scheduler, (metabase), (jupyter)
├── docker/                   # Dockerfiles + entrypoints
├── pyproject.toml            # uv-managed
├── .env.example              # every var documented; .env is gitignored
├── src/emeye/
│   ├── cli/                  # Typer app; thin — delegates to services
│   ├── config.py             # pydantic-settings; single source of env truth
│   ├── http/                 # rate-limited client, cache, retry, UA policy
│   ├── sources/              # one module per upstream (beatport, musicbrainz, …)
│   │   └── <source>/         # client.py, parse.py, models.py, ingest.py
│   ├── db/                   # engine, session, schema, alembic/
│   ├── domain/               # keys, camelot, genres, mix-name grammar, normalization
│   ├── entities/             # entity resolution: artists, labels, tracks
│   ├── analytics/            # metric definitions computed in Python
│   ├── forecast/             # models, backtesting harness, evaluation
│   └── export/               # Parquet/CSV dumps for DuckDB + notebooks
├── dbt/                      # dbt project: staging → intermediate → marts
├── app/                      # Streamlit exploration UI
├── notebooks/                # exploratory; cleared of output before commit
├── tests/                    # unit, integration (needs pg), fixtures/
├── docs/
│   ├── DATA-SOURCES.md       # per-source access, fields, limits, legal posture
│   ├── DOMAIN.md             # genre taxonomy, keys/Camelot, title grammar
│   └── ARCHITECTURE.md       # data flow, layering, schema contracts
├── .planning/                # GSD artifacts — PROJECT, REQUIREMENTS, ROADMAP, STATE
└── gsd-core/                 # vendored context-engineering framework (UNTRACKED)
```

---

## Architecture

Medallion (bronze → silver → gold), one direction only.

```
  upstream APIs / HTML                 bronze (raw, immutable)
  ┌──────────────────┐   ingest    ┌─────────────────────────────┐
  │ Beatport         │ ──────────► │ raw_documents               │
  │ MusicBrainz      │             │  source, endpoint, params,  │
  │ Discogs          │             │  fetched_at, http_status,   │
  │ Deezer           │             │  payload (JSONB/compressed),│
  │ Last.fm          │             │  content_hash               │
  │ ListenBrainz     │             └──────────────┬──────────────┘
  └──────────────────┘                            │ parse (replayable)
                                                  ▼
                              silver (normalized, deduped, resolved)
                              ┌───────────────────────────────────┐
                              │ dim_artist, dim_label, dim_genre  │
                              │ dim_track, fct_release,           │
                              │ fct_chart_position (daily),       │
                              │ bridge_track_artist(role),        │
                              │ xref_external_id (MBID/ISRC/…)    │
                              └──────────────┬────────────────────┘
                                             │ dbt models + tests
                                             ▼
                                gold (analysis-ready marts)
                              ┌───────────────────────────────────┐
                              │ mart_tempo_by_genre_month         │
                              │ mart_key_distribution_month       │
                              │ mart_title_token_month            │
                              │ mart_label_share_month            │
                              │ mart_artist_activity_month        │
                              │ mart_forecast_run / _point        │
                              └──────────────┬────────────────────┘
                                             ▼
                          Streamlit · notebooks · Parquet exports · DuckDB
```

**Non-negotiable invariants**

1. **Bronze is append-only and never edited.** Every parse must be replayable
   from bronze without re-fetching. If a parser is wrong, fix it and reparse.
2. **Provenance on every row.** Silver rows carry `source`, `source_row_id`,
   `first_seen_at`, `last_seen_at`, and the bronze `content_hash` they derive from.
3. **Idempotent ingestion.** Re-running any job for a date must not duplicate
   rows. Natural keys + `ON CONFLICT DO UPDATE`.
4. **Charts are facts with a date grain**, never mutated in place. A track's
   position on 2026-03-01 is a separate row from 2026-03-02.
5. **Nothing derived is stored in silver.** Camelot codes, title tokens,
   normalized names, and BPM buckets are computed in dbt (gold) or in
   `domain/`, so redefining them is a rebuild, not a migration.
6. **No analytics query reads bronze.** If a mart needs a field, promote it.

---

## Domain rules Claude must not improvise

Full detail in `docs/DOMAIN.md`. The load-bearing ones:

- **Key notation.** Beatport uses `A min` / `F♯ maj`; MusicBrainz/Deezer differ.
  Store a canonical `(tonic_pc, mode)` pair (pitch class 0–11 + major/minor) and
  derive Camelot/Open Key on read. Never store the display string as the key.
- **Enharmonics are the same key.** `D♯ min` == `E♭ min`. Normalize on ingest.
- **BPM is ambiguous by a factor of two.** Half/double-time reporting is common
  (e.g. drum & bass tagged at 87 vs 174, dubstep at 70 vs 140). Store raw BPM as
  reported, plus a genre-aware `bpm_canonical` folded into that genre's expected
  band. Never silently overwrite the reported value.
- **Mix name is not part of the title.** `Track Title (Someone Remix)` decomposes
  into `title`, `mix_name`, `remixer[]`, and a `mix_kind` enum
  (`original`, `extended`, `radio_edit`, `remix`, `rework`, `vip`, `dub`,
  `edit`, `live`, `instrumental`, `bootleg`, `tool`). Parse once, in `domain/`.
- **Genre taxonomies drift.** Beatport has repeatedly renamed and split genres
  (e.g. Techno split into Peak Time/Driving and Raw/Deep/Hypnotic; Afro House,
  Organic House, Amapiano added). Model genres as a versioned dimension with a
  crosswalk to a stable internal taxonomy, otherwise every long-run series
  breaks at the rename date.
- **Artist strings are not artists.** `A & B`, `A feat. B`, `A vs B`,
  `A presents B` and alias/live-name splits all need parsing plus an alias table.
  Link to MusicBrainz MBIDs where possible; never treat the display string as an ID.
- **ISRC is the best cross-service join key**, but is missing, duplicated, and
  occasionally wrong. Treat it as a strong hint, not a primary key.
- **Re-releases, remasters and compilations inflate counts.** Deduplicate on
  (normalized title, mix name, artist set, duration bucket) before counting
  "releases", and keep the raw count available for comparison.
- **Release date ≠ availability date.** Beatport exclusives commonly precede
  wide release by 2–4 weeks. Track both when both exist and pick one grain
  explicitly per metric.

---

## Data sources

Detail, field lists, and limits live in `docs/DATA-SOURCES.md`. Summary:

| Source | Access | Gives us | Posture |
|---|---|---|---|
| **Beatport** | No open public API; v4 API is partner-gated. Web payloads are the practical route | BPM, key, genre/subgenre, label, catalog no., remixer credits, release date, **charts** | Primary. Handle with maximum care — see legal posture below |
| **MusicBrainz** | Open API + full DB dumps | Canonical artists/releases, MBIDs, ISRCs, **remixer relationships**, aliases | Backbone for entity resolution. 1 req/s, descriptive User-Agent required |
| **Discogs** | Free API (token) + monthly data dumps | Labels, catalog numbers, styles, credits, historical/vinyl depth | Best label and credit coverage. Prefer the dumps for bulk |
| **Deezer** | Public API, no auth for most reads | **BPM**, duration, ISRC, release date, artist/album links | Free, unauthenticated tempo cross-check |
| **Last.fm** | Free API key | Tags, playcounts, listeners | Popularity proxy over time; tags are folksonomy, treat as noisy |
| **ListenBrainz** | Open API + data dumps | Real listening counts, MBID-keyed | Clean, open alternative to Last.fm |
| **Spotify** | OAuth | Popularity, release metadata | ⚠️ `audio-features` / `audio-analysis` were **deprecated for new apps in Nov 2024** — do **not** design tempo/key analytics around Spotify |
| **Traxsource / Juno** | HTML | House/techno coverage Beatport under-represents | Optional, later phase |
| **1001Tracklists** | No API, aggressive anti-bot | What DJs actually play | Out of scope for now; revisit only if a sanctioned route appears |
| **Local audio (Essentia/librosa)** | Owner's own files | Ground-truth BPM/key for validation | Optional; the only way to audit vendor key accuracy |

### Legal & ethical posture — binding

This project is for personal analysis only. When writing any collector:

1. **Read and honor `robots.txt`** for every host, every run.
2. **Rate limit conservatively** — default ≤1 request/second per host, with
   jitter, exponential backoff, and hard respect for `429` / `Retry-After`.
3. **Identify honestly** via a descriptive `User-Agent` including a contact
   address. Never impersonate a browser to defeat bot detection.
4. **Never** solve CAPTCHAs, rotate proxies/IPs, spoof fingerprints, or use
   another person's credentials.
5. **Cache aggressively.** Bronze exists so we never re-fetch the same document.
   A cache hit is always preferred over a request.
6. **Do not redistribute** raw third-party payloads. Exports for the owner's own
   analysis only; no public dataset, no scraped-content mirror in git.
7. **Prefer the open source over the closed one.** If MusicBrainz/Discogs/Deezer
   can answer the question, do not ask Beatport.
8. If a source's Terms of Service prohibit automated access, say so plainly in
   `docs/DATA-SOURCES.md`, keep the collector behind an explicit opt-in flag,
   and let the owner make the call. Do not quietly enable it.

Scraping volume is a personal-use trickle by design. If a design needs more
throughput than that, the design is wrong.

---

## Analytics conventions

- **Monthly is the default reporting grain**; daily for chart snapshots.
  Weekly only where a metric genuinely needs it.
- **Every metric has one definition, in one place** — a dbt model or a function
  in `analytics/`. Notebooks import it; they never redefine it.
- **Distributions over means.** BPM and key are multi-modal; report median, IQR,
  and modal peaks. A mean BPM across genres is a meaningless number.
- **Always report the denominator.** "Techno got faster" must come with the
  release count behind it; small-n months are noise.
- **Separate catalog signal from chart signal.** Catalog = what was released
  (unbiased-ish). Charts = what sold/was promoted (heavily biased). Never
  blend them into one series without labelling it.
- **Mind the coverage ramp.** Our own collection starts on day one of ingest;
  a metric that rises simply because we started collecting more is a bug.
  Every series carries a `coverage_note` and a first-reliable-date.
- **Known seasonality:** Amsterdam Dance Event (October), Miami Music Week
  (March), Ibiza season (May–Sept), December holiday slump, January reissue
  wave. Deseasonalize before claiming a trend.

## Forecasting conventions

- **Baselines first, always:** seasonal naive and drift. A model that cannot
  beat seasonal-naive on backtest does not ship.
- **Rolling-origin backtesting** (expanding window), never a random split.
  Time leakage is the default failure mode here.
- **Report MASE and sMAPE** plus prediction intervals. Point forecasts alone
  are not a deliverable.
- **Persist every run**: model id, params, training window, feature set, code
  version, and the forecast rows. Forecasts are data, and their accuracy gets
  measured later against what actually happened.
- Model progression: seasonal naive → ETS/Holt-Winters → SARIMAX → gradient
  boosting on lag/calendar features. Stop as soon as accuracy plateaus.
- **Honesty about horizon.** With <24 months of history, anything beyond a
  3-month horizon is decoration. State it in the output.

---

## Code conventions

- **Formatting/lint:** `ruff format` + `ruff check --fix`. Line length 100.
- **Typing:** mypy on `src/`; new modules must type-check clean. No bare `Any`
  in public signatures.
- **Errors:** no silent `except Exception: pass`. Ingest failures are recorded
  in an `ingest_run` table with status and error text, then re-raised or skipped
  deliberately.
- **Logging:** `structlog`-style key/value logs to stdout. Every ingest logs
  source, endpoint, item count, cache hit/miss, and duration.
- **No network calls at import time.** Ever.
- **SQL style:** lowercase keywords, one column per line in `SELECT`, CTEs over
  nested subqueries, explicit `JOIN … ON`. Table naming: `dim_`, `fct_`,
  `bridge_`, `xref_`, `stg_`, `int_`, `mart_`.
- **Migrations:** every schema change is an Alembic revision with a downgrade.
  Never edit an applied migration.
- **Tests:** unit tests for all parsing/normalization (these are where the bugs
  live), integration tests against a throwaway Postgres, and a recorded-fixture
  test per source client. HTTP in tests is mocked — no exceptions.
- **Secrets:** only via env / `.env`. If you find a credential in a diff, stop
  and tell the owner.
- **Commits:** conventional-commit style (`feat:`, `fix:`, `chore:`, `docs:`).
  One logical change per commit.

---

## Working in this repo

```bash
make up          # start postgres + app containers
make migrate     # alembic upgrade head
make ingest      # run today's collectors
make dbt         # build + test silver/gold models
make test        # pytest
make lint        # ruff + mypy
make app         # streamlit exploration UI
make psql        # shell into the warehouse
```

Everything runs in containers. If a command needs a host-level tool other than
Docker, that is a bug in the Makefile.

---

## GSD workflow

`gsd-core/` is a vendored clone of [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core),
a context-engineering / spec-driven development framework. It is **untracked on
purpose** (see `.gitignore`) — it is reference material and tooling, not part of
this project's source. Refresh it with `git -C gsd-core pull`.

Use it as the working method:

1. **Discuss** — settle implementation decisions before planning.
2. **Plan** — research and decompose the phase into plans that fit one context.
3. **Execute** — run plans in fresh-context subagents.
4. **Verify** — walk through what was built; fix before declaring done.
5. **Ship** — commit, archive the phase, move to the next.

Project artifacts live in `.planning/`:

| File | Purpose |
|---|---|
| `PROJECT.md` | Living project context: value, scope, decisions |
| `REQUIREMENTS.md` | Numbered requirements (REQ-xx) traced to phases |
| `ROADMAP.md` | Phase breakdown, dependencies, success criteria |
| `STATE.md` | Current position and accumulated context — read this first |
| `config.json` | Workflow preferences |

Useful skills are in `gsd-core/skills/` (`gsd-plan-phase`, `gsd-execute-phase`,
`gsd-validate-phase`, `gsd-ship`, `gsd-debug`, …). They assume a GSD install via
`npx @opengsd/gsd-core@latest`; until that install happens, read the SKILL.md
files directly and follow them by hand.

---

## Agent working agreements

**Do**

- Read `.planning/STATE.md` and `.planning/ROADMAP.md` before proposing work.
- Keep changes inside the current phase's scope.
- Write the parser test before the parser.
- Record any upstream quirk you discover (weird field, inconsistent key format,
  silent pagination cap) in `docs/DATA-SOURCES.md` immediately. That knowledge
  is expensive to rediscover.
- Update `.planning/STATE.md` and the ROADMAP progress table when a plan lands.
- Ask before adding a dependency, a new upstream source, or a new container.

**Don't**

- Don't hit live upstream services from tests or during development iteration —
  use bronze fixtures.
- Don't invent field semantics. If a Beatport field's meaning is unclear, sample
  bronze rows and document the finding rather than guessing.
- Don't add cloud, auth, or multi-user machinery.
- Don't backfill by hammering an upstream. Bulk needs come from data dumps.
- Don't delete or rewrite bronze data to "clean" it.
- Don't commit notebook outputs, `.env`, database dumps, or scraped payloads.

---

## Open questions for the owner

Tracked in `.planning/PROJECT.md` and resolved during Discuss steps:

1. Which genres are in scope for v1 — everything Beatport lists, or a focused
   set (e.g. Techno, Tech House, Melodic H&T, DnB, Trance)?
2. Is there an existing personal library / DJ history to fold in as ground truth?
3. Does the owner have Discogs / Last.fm accounts for API tokens?
4. Retention: keep bronze payloads forever (grows GBs/year), or compress and
   prune after N months?
5. Backup target for the Postgres volume — external disk, or none?
