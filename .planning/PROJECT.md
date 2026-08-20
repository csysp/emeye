# emeye (Electronic Music Eye)

## What This Is

A personal, local-first data warehouse and analysis toolkit for electronic and
club music production trends. It ingests catalog and chart data from Beatport
plus free open-music APIs, normalizes it into a PostgreSQL warehouse, and
produces long-horizon trend analytics and forecasts over tempo, key, song-title
language, label dominance, and artist/remixer activity. Single user, runs
entirely in Docker on the owner's machine.

## Core Value

A trustworthy, continuously-growing longitudinal dataset of the electronic music
release landscape — every other feature is replaceable, the history is not.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] REQ-01 — Whole system runs from `docker compose up` on Linux/macOS/Windows
- [ ] REQ-02 — Raw upstream payloads land immutably in bronze and parsing is replayable
- [ ] REQ-03 — Daily Beatport chart snapshots captured without gaps
- [ ] REQ-04 — Beatport catalog metadata (BPM, key, genre, label, credits, dates) ingested
- [ ] REQ-05 — Open sources (MusicBrainz, Discogs, Deezer, Last.fm, ListenBrainz) enrich and cross-check
- [ ] REQ-06 — Entities resolved across sources via ISRC/MBID/fuzzy with confidence tracking
- [ ] REQ-07 — Titles decomposed into title / mix name / mix kind / remixers / features
- [ ] REQ-08 — Keys canonicalized to (tonic, mode) with Camelot derived on read
- [ ] REQ-09 — BPM stored as reported plus genre-aware canonical fold
- [ ] REQ-10 — Genre taxonomy versioned with a crosswalk to a stable internal taxonomy
- [ ] REQ-11 — Analytics marts for tempo, key, title tokens, label share, artist activity
- [ ] REQ-12 — Chart-derived and catalog-derived series are distinguishable everywhere
- [ ] REQ-13 — Forecasting with rolling-origin backtesting and mandatory baselines
- [ ] REQ-14 — Forecast runs persisted and scored against actuals over time
- [ ] REQ-15 — Streamlit exploration UI over the marts
- [ ] REQ-16 — Parquet export for DuckDB/notebook analysis
- [ ] REQ-17 — Scheduled, idempotent, individually re-runnable jobs
- [ ] REQ-18 — Collectors are polite: robots.txt, rate limits, honest UA, opt-in gating
- [ ] REQ-19 — `emeye status` surfaces ingest health from `ingest_run`
- [ ] REQ-20 — `emeye backup` produces a restorable warehouse dump
- [ ] REQ-30 — Repository carries a strong protective (copyleft) license, applied consistently
- [ ] REQ-31 — Runtime dependencies are license-compatible with that choice, checked in CI

### Out of Scope

- Multi-user support, auth, RBAC — single-user personal tool; adds cost, no value
- Cloud deployment / managed services — local-first is a requirement, not a stage
- Public API or dataset redistribution — third-party terms forbid it
- Real-time / streaming ingestion — batch answers every question we have
- Anti-bot evasion (CAPTCHA solving, proxy rotation, fingerprint spoofing) — line we don't cross
- 1001Tracklists collection — no sanctioned route; explicit anti-automation terms
- Spotify audio-features-based tempo/key analysis — deprecated for new apps (Nov 2024)
- Audio playback / DJ tooling / library management — different product
- Mobile or native clients — browser on localhost is enough

## Context

- **Domain:** electronic/club music release data. The interesting questions are
  longitudinal: is techno actually getting faster, is minor-key dominance
  shifting, are labels consolidating, what happens to a title's language over a
  decade, who is remixing whom.
- **The hard constraint:** chart data is a snapshot and cannot be recovered
  retroactively. Catalog metadata mostly can. This asymmetry drives phase order.
- **Beatport is the only source carrying BPM + key + DJ-oriented genre across
  the whole commercial landscape**, and it has no open API. Open sources
  (MusicBrainz, Discogs, Deezer, ListenBrainz) provide the entity backbone,
  cross-checks and bulk dumps.
- **Every vendor taxonomy drifts.** Beatport has repeatedly split and renamed
  genres; a series keyed on the vendor string breaks at each rename and the
  break looks like a trend. Handled via a versioned genre dimension + crosswalk.
- **Vendor key/BPM detection is algorithmic and imperfect.** Local audio
  analysis of owned files is the only available ground truth.
- Development method is GSD Core, vendored untracked at `gsd-core/`.

## Constraints

- **Tech stack**: Python 3.12 + PostgreSQL 16 + dbt-core — owner's stated choice: Python for scraping/analysis, SQL for the warehouse
- **Deployment**: Docker Compose only — must be system-agnostic; Docker is the sole host dependency
- **Scale**: single user, batch — no concurrency, HA, or throughput requirements
- **Budget**: free sources only — no paid APIs or hosted services
- **Legal**: personal research use; polite collection; no redistribution — third-party ToS
- **Data**: chart history is unrecoverable if not captured daily — forces ingest-before-analytics phase order

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PostgreSQL as system of record, DuckDB for ad-hoc | Postgres suits incremental idempotent upserts; DuckDB is better for exploratory scans over Parquet exports | — Pending |
| dbt-core for silver→gold | Owner wants SQL-centric analytics; gives tests, lineage and cheap redefinition of derived metrics | — Pending |
| Medallion (bronze/silver/gold) with immutable bronze | Parsers will be wrong; replayability from raw payloads avoids ever re-scraping | — Pending |
| Derived fields (Camelot, tokens, BPM buckets) computed downstream, not stored in silver | Definitions will change; a rebuild is cheaper than a migration | — Pending |
| Typer CLI + cron container instead of Dagster/Prefect | Job graph is shallow; an orchestrator would be more machinery than the problem needs | — Pending |
| Charts ingestion ships before analytics | Chart snapshots are irrecoverable; analytics can be built against data already collected | — Pending |
| Beatport collector behind an explicit opt-in flag | ToS prohibits automated collection; the owner should make that choice consciously | — Pending |
| Spotify excluded as a tempo/key source | `audio-features` deprecated for new apps Nov 2024; building on it would strand the analytics | — Pending |
| Strong protective (copyleft) license, AGPL-3.0-or-later recommended | The Streamlit surface makes this network-deployable, so a plain GPL leaves the SaaS loophole open; AGPL also keeps Essentia (AGPL-3.0) usable for the deferred audio ground-truth work | — Pending (decided in plan 01-04) |
| Store keys as (tonic_pc, mode), render Camelot on read | Enharmonic spellings otherwise split one key into phantom duplicates | — Pending |
| Genre modelled as SCD2 + canonical crosswalk | Vendor taxonomy renames otherwise fabricate false trend breaks | — Pending |

## Open Questions

1. Genre scope for v1 — all Beatport genres, or a focused subset?
2. Is there a personal library / DJ history to fold in as ground truth?
3. Discogs / Last.fm accounts available for API tokens?
4. Bronze retention — keep forever, or compress and prune after N months?
5. Backup target for the Postgres volume?
6. Does the owner have (or want to pursue) sanctioned Beatport API access?
7. License: AGPL-3.0-or-later (recommended), GPL-3.0-or-later, or a
   source-available non-commercial licence? Decided at the 01-04 checkpoint.

---
*Last updated: 2026-08-20 after project initialization*
