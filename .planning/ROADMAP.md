# Roadmap: emeye (Electronic Music Eye)

## Overview

Build a local Docker warehouse, then get data flowing before anything clever
happens — chart snapshots are irrecoverable, so ingestion outranks analysis in
phase order. Once Beatport catalog and charts are landing daily and open sources
have enriched and cross-checked them, normalize the messy parts of the domain
(titles, keys, tempo, genre drift) in SQL, build the trend marts, add
forecasting with honest backtesting, and finish with an exploration UI and the
operational bits that keep a decade-long dataset alive.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation** - Licensing, Docker Compose warehouse, CLI skeleton, migrations, CI
- [ ] **Phase 2: Ingestion Framework** - Bronze store, polite HTTP layer, run tracking, idempotent jobs
- [ ] **Phase 3: Beatport Connector** - Catalog + daily chart snapshots landing in bronze and silver
- [ ] **Phase 4: Open-Data Enrichment** - MusicBrainz, Discogs, Deezer, Last.fm/ListenBrainz + entity resolution
- [ ] **Phase 5: Domain Normalization** - Titles, keys, tempo folding, genre crosswalk in silver/dbt
- [ ] **Phase 6: Trend Analytics** - Tempo, key, title, label and artist marts with honest denominators
- [ ] **Phase 7: Forecasting** - Backtesting harness, baselines, models, persisted and scored forecasts
- [ ] **Phase 8: Exploration & Operations** - Streamlit UI, Parquet/DuckDB export, backup, retention

## Phase Details

### Phase 1: Foundation
**Goal**: A cloned repo becomes a running, empty warehouse with one command, under a license that protects the work, with the quality gates that keep it honest in place from commit one.
**Depends on**: Nothing (first phase)
**Requirements**: REQ-01, REQ-24, REQ-25, REQ-27, REQ-29, REQ-30
**Success Criteria** (what must be TRUE):
  1. `make up && make migrate` on a fresh clone yields a running Postgres with schema applied, with Docker as the only host dependency
  2. `emeye --help` runs inside the container and lists command groups
  3. `make lint` and `make test` pass and run the identical commands CI runs
  4. Tests execute with networking disabled
  5. No credential or third-party payload can be committed (gitignore + CI check)
  6. The repository carries a deliberately chosen strong protective license, applied consistently across LICENSE, packaging metadata and source headers, with dependency compatibility verified
**Plans**: 4 plans

Plans:
- [ ] 01-01: Python project — uv, Typer CLI skeleton, pydantic-settings config, structured logging
- [ ] 01-02: Container stack — Dockerfile, compose (postgres + app), Makefile, .env.example, Alembic wiring
- [ ] 01-03: Quality gates — ruff, mypy, pytest, pre-commit, CI workflow, secret/payload checks
- [ ] 01-04: Licensing & governance — choose and apply a strong protective license, verify dependency compatibility

### Phase 2: Ingestion Framework
**Goal**: A reusable, polite, replayable ingestion substrate — so every later connector is a thin adapter rather than its own snowflake.
**Depends on**: Phase 1
**Requirements**: REQ-02, REQ-17, REQ-18, REQ-19, REQ-21, REQ-23
**Success Criteria** (what must be TRUE):
  1. Any fetched document lands in bronze with source, params, timestamp, status and content hash
  2. Re-fetching an unchanged document is a no-op, and re-running any job twice changes no row counts
  3. Rate limiting, robots.txt checks, backoff and `Retry-After` are enforced centrally, not per-source
  4. `emeye status` reports per-source last run, counts, duration, cache hit rate and errors
  5. A failed ingest leaves silver untouched and is visible in `ingest_run`
**Plans**: 3 plans

Plans:
- [ ] 02-01: Bronze schema (`raw_document`, `ingest_run`) + migrations + replay/reparse command
- [ ] 02-02: HTTP layer — rate limiter, robots.txt, retry/backoff, honest UA, cache-by-hash, opt-in source gating
- [ ] 02-03: Job runner — idempotent job contract, run tracking, `emeye status`, scheduler container

### Phase 3: Beatport Connector
**Goal**: The irreplaceable data starts accumulating — Top 100 and Hype 100 snapshots on every chart reset, plus catalog metadata for the tracks that appear on them.
**Depends on**: Phase 2
**Requirements**: REQ-03, REQ-04, REQ-17, REQ-23, REQ-26
**Scope note**: Overall **Top 100** and **Hype 100** only — no per-genre chart sweep. Catalog detail is fetched only for track IDs not already in the warehouse, so request volume falls as the catalogue fills. No sanctioned/partner API is pursued.
**Success Criteria** (what must be TRUE):
  1. Top 100 and Hype 100 snapshots land as dated facts on each chart reset and never mutate in place
  2. One chart fetch per chart per reset — a re-run inside the same reset window serves from bronze and issues zero requests
  3. Catalog rows carry BPM, key, genre string, label, catalog number, artists, remixers, both date fields, ISRC and length, matching the source on spot checks
  4. Track detail is fetched only for previously unseen track IDs
  5. Missing chart resets are detected and reported rather than silently absent
  6. Parsers fail loudly on unexpected payload shape instead of emitting nulls
  7. The connector is disabled by default and requires a deliberate opt-in setting
**Plans**: 4 plans

Plans:
- [ ] 03-01: Access spike — establish the chart reset cadence, the minimum viable request set, and robots.txt posture; document findings
- [ ] 03-02: Chart collector — Top 100 + Hype 100 dated snapshots, chart dimension, reset-gap detection
- [ ] 03-03: Catalog collector — track/release/label/artist detail for unseen IDs only, bronze + silver upserts
- [ ] 03-04: Parser fixture corpus + unit tests + failure-mode handling

### Phase 4: Open-Data Enrichment
**Goal**: Break the single-source dependency — an independent view of the same tracks, a real entity backbone, and a second chart population from streaming.
**Depends on**: Phase 3
**Requirements**: REQ-05, REQ-06, REQ-32
**Success Criteria** (what must be TRUE):
  1. MusicBrainz supplies MBIDs, aliases, ISRCs and remixer relationships for a measurable share of the charted catalog
  2. Deezer supplies an independent BPM for cross-checking, and the disagreement rate against Beatport is quantified
  3. Discogs label hierarchy, credits and styles are loaded from data dumps rather than API crawling
  4. Spotify playlist membership is captured as dated facts for the tracked dance playlists, via the official API
  5. No Spotify tempo or key field is read anywhere in the codebase
  6. Popularity snapshots (Last.fm/ListenBrainz) accumulate on a schedule so deltas are derivable
  7. Every cross-source link records confidence and method, and re-resolution never downgrades a link
**Plans**: 5 plans

Plans:
- [ ] 04-01: MusicBrainz client + relationship/alias/ISRC ingest (1 req/s, dump path for bulk)
- [ ] 04-02: Deezer + Last.fm/ListenBrainz collectors, scheduled popularity snapshots
- [ ] 04-03: Discogs data-dump loader — labels, credits, styles
- [ ] 04-04: Spotify connector — client-credentials auth, playlist membership snapshots, ISRC/metadata capture
- [ ] 04-05: Entity resolution — ISRC → MBID → fuzzy composite, `xref_external_id`, review queue

### Phase 5: Domain Normalization
**Goal**: Turn messy vendor strings into analyzable structure — the phase that decides whether every later number is real or an artifact.
**Depends on**: Phase 4
**Requirements**: REQ-07, REQ-08, REQ-09, REQ-10, REQ-26, REQ-33
**Success Criteria** (what must be TRUE):
  1. Titles decompose into title, mix name, mix kind, remixers and featured artists, with unparsed cases flagged rather than dropped
  2. Enharmonic key spellings collapse to one canonical key and Camelot round-trips both ways
  3. BPM is stored as reported plus a genre-aware canonical fold, and no row is dropped for being out of band
  4. A vendor genre rename produces no discontinuity in the canonical genre series
  5. Artist display strings resolve into roles (primary/featured/remixer) without inflating artist output counts
**Plans**: 4 plans

Plans:
- [ ] 05-01: Title/mix-name grammar parser + oddity fixture corpus
- [ ] 05-02: Key canonicalization + Camelot/Open Key derivation
- [ ] 05-03: Tempo folding with per-genre bands, reported value preserved
- [ ] 05-04: Genre SCD2 + canonical taxonomy + crosswalk; artist role/alias splitting

### Phase 6: Trend Analytics
**Goal**: Answer the actual questions — with denominators, population labels and coverage caveats attached so the answers survive scrutiny.
**Depends on**: Phase 5
**Requirements**: REQ-11, REQ-12, REQ-28
**Success Criteria** (what must be TRUE):
  1. Tempo, key, title-token, label-share, artist-activity and remix-network marts build and pass dbt tests
  2. Every mart row carries its population (catalog vs chart), its denominator and a coverage note
  3. Tempo is reported as median/IQR/modes, never as a bare cross-genre mean
  4. Label concentration is reported as top-N share and HHI per genre per period
  5. Genre taxonomy break dates are available as an annotation layer on every long-run series
**Plans**: 4 plans

Plans:
- [ ] 06-01: dbt project scaffolding — staging/intermediate layers, tests, coverage-note convention
- [ ] 06-02: Tempo + key marts with distributional statistics
- [ ] 06-03: Title-token and mix-kind marts (token share, length inflation)
- [ ] 06-04: Label share/HHI, artist activity/churn, remix-network marts

### Phase 7: Forecasting
**Goal**: Project trends forward with enough rigor that the forecasts are worth storing — and grade them later against what actually happened.
**Depends on**: Phase 6
**Requirements**: REQ-13, REQ-14
**Success Criteria** (what must be TRUE):
  1. Backtesting is rolling-origin with expanding windows; no random splits exist in the codebase
  2. Every target gets seasonal-naive and drift baselines in the same run as any model
  3. A model that fails to beat its baseline on MASE is reported as such and not promoted
  4. Every forecast run persists model id, params, training window, feature set, code version, and prediction intervals
  5. Forecast accuracy is recomputed against actuals as new months arrive
**Plans**: 3 plans

Plans:
- [ ] 07-01: Backtest harness, evaluation metrics (MASE/sMAPE), baseline models
- [ ] 07-02: Model progression — ETS/Holt-Winters, SARIMAX, gradient boosting on lag/calendar features
- [ ] 07-03: Forecast persistence, run registry, rolling accuracy scoring vs actuals

### Phase 8: Exploration & Operations
**Goal**: Make the dataset usable day to day, and durable enough to still be here in ten years.
**Depends on**: Phase 7
**Requirements**: REQ-15, REQ-16, REQ-20, REQ-22
**Success Criteria** (what must be TRUE):
  1. Streamlit renders tempo, key, title, label, artist and forecast-vs-actual views over the marts
  2. `emeye export` produces Parquet that opens in DuckDB with no Postgres connection
  3. `emeye backup` produces a dump that restores into an empty Postgres and rebuilds marts
  4. Bronze retention is an explicit configurable policy, never a silent default
  5. A missed scheduled run is visible without going looking for it
**Plans**: 3 plans

Plans:
- [ ] 08-01: Streamlit app with saved views over the marts
- [ ] 08-02: Parquet export + DuckDB workflow + notebook conventions
- [ ] 08-03: Backup/restore, retention policy, scheduler health surfacing

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/4 | Not started | - |
| 2. Ingestion Framework | 0/3 | Not started | - |
| 3. Beatport Connector | 0/4 | Not started | - |
| 4. Open-Data Enrichment | 0/5 | Not started | - |
| 5. Domain Normalization | 0/4 | Not started | - |
| 6. Trend Analytics | 0/4 | Not started | - |
| 7. Forecasting | 0/3 | Not started | - |
| 8. Exploration & Operations | 0/3 | Not started | - |

## Deferred / Later Milestones

Candidates for v1.1+, deliberately not in the v1.0 roadmap:

- Traxsource / Juno collectors — test whether observed trends are Beatport bias
- Local audio analysis (Essentia/librosa) as key/BPM ground truth
- Resident Advisor event data — correlate chart success with booking activity
- Remix-network graph analysis (communities, centrality, scene detection)
- Metabase container for click-through SQL exploration
- Internet Archive best-effort backfill of historical Beatport charts
