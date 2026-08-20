# Requirements: emeye

Numbered requirements traced to roadmap phases. `REQ-xx` ids are stable; when a
requirement is invalidated it moves to Out of Scope in `PROJECT.md` rather than
being renumbered or deleted.

## Functional

| ID | Requirement | Phase | Acceptance |
|---|---|---|---|
| REQ-01 | The whole system starts with `docker compose up` on Linux, macOS and Windows/WSL2 | 1 | Fresh clone → `make up && make migrate` succeeds with only Docker installed |
| REQ-02 | Raw upstream payloads are stored immutably; parsing is replayable without re-fetching | 2 | `emeye reparse <source>` rebuilds silver from bronze alone, offline |
| REQ-03 | Daily Beatport chart snapshots are captured with no gaps | 3 | `fct_chart_position` has one row set per chart per day since ingest start; gaps are detected and reported |
| REQ-04 | Beatport catalog metadata is ingested: BPM, key, genre/subgenre, label, catalog no., artists, remixers, both date fields, ISRC, length | 3 | Sampled tracks match the source page field-for-field |
| REQ-05 | Open sources enrich and cross-check the catalog: MusicBrainz, Discogs, Deezer, Last.fm, ListenBrainz | 4 | ≥1 independent BPM value available for a measurable share of tracks; disagreement rate reported |
| REQ-06 | Entities are resolved across sources with confidence and method recorded | 4 | `xref_external_id` carries confidence + method; re-running resolution never lowers an existing link's confidence |
| REQ-07 | Titles decompose into title, mix_name, mix_kind, remixers, featured artists | 5 | Fixture corpus of real-world oddities parses correctly; unparsed cases are flagged, never silently dropped |
| REQ-08 | Keys are canonical `(tonic_pc, mode)`; Camelot/Open Key derived on read | 5 | Round-trip tests both directions; enharmonic inputs collapse to one key |
| REQ-09 | BPM stored as reported plus a genre-aware canonical fold | 5 | Both columns present; no row is ever dropped for being out of band |
| REQ-10 | Genre is captured as a per-track attribute with the vendor string preserved verbatim | 5 | Genre is queryable per track; no crosswalk required at charts-only scope (versioned taxonomy deferred — see PROJECT.md Key Decisions) |
| REQ-11 | Analytics marts exist for tempo, key, title tokens, label share, artist activity, remix network | 6 | Each mart builds and passes dbt tests; each reports its denominator |
| REQ-12 | Chart-derived and catalog-derived series are distinguishable everywhere | 6 | Every mart row carries `population`; no mart blends the two |
| REQ-13 | Forecasting uses rolling-origin backtesting with mandatory baselines | 7 | Every target has seasonal-naive + drift baselines computed in the same run |
| REQ-14 | Forecast runs are persisted and scored against actuals over time | 7 | `mart_forecast_point` joins to actuals; MASE/sMAPE recomputed as history arrives |
| REQ-15 | A Streamlit UI explores the marts with saved views | 8 | Tempo, key, titles, labels, artists and forecast-vs-actual views all render |
| REQ-16 | Marts export to Parquet for DuckDB and notebook analysis | 8 | `emeye export` output opens in DuckDB with no Postgres connection |

## Operational

| ID | Requirement | Phase | Acceptance |
|---|---|---|---|
| REQ-17 | All jobs are scheduled, idempotent, and individually re-runnable | 2, 3 | Running any job twice for the same date changes no row counts |
| REQ-19 | `emeye status` surfaces ingest health from `ingest_run` | 2 | Shows last run, counts, duration, cache hit rate, errors per source |
| REQ-20 | `emeye backup` produces a restorable warehouse dump | 8 | Dump restores into an empty Postgres and marts rebuild |
| REQ-21 | Ingest failures are recorded and never corrupt silver | 2 | Silver derives only from complete bronze rows; a failed run leaves silver unchanged |
| REQ-22 | Storage growth is bounded by an explicit, configurable retention policy | 8 | Retention is a documented config value, never a silent default |

## Compliance

| ID | Requirement | Phase | Acceptance |
|---|---|---|---|
| REQ-18 | Collectors honor robots.txt, rate limits, honest User-Agent, and `Retry-After` | 2 | Rate limiter and robots check are enforced in the shared HTTP layer, not per-source |
| REQ-23 | Sources whose terms prohibit automated access are gated behind explicit opt-in | 2, 3 | Default config disables them; enabling requires a deliberate setting |
| REQ-24 | No third-party payloads are committed or redistributed | 1 | `.gitignore` covers data/exports; CI check rejects payload files in a diff |
| REQ-25 | No credentials in the repo | 1 | `.env` gitignored, `.env.example` documents every variable, secret scan in CI |
| REQ-30 | The repository carries a strong protective (copyleft) license, applied consistently | 1 | `LICENSE` present, `pyproject.toml` metadata matches, source headers consistent, choice recorded as a Key Decision |
| REQ-31 | Every runtime dependency is license-compatible with the chosen license | 1, and on every dependency addition | A license inventory is generated and checked in CI; an incompatible dependency fails the build |
| REQ-32 | Spotify supplies playlist/chart membership and track metadata via the official API, never tempo or key | 4 | Dated playlist-membership facts accumulate; no analytic reads a Spotify tempo/key field |
| REQ-33 | BPM is resolved through an ordered, recorded fallback ladder | 5 | Every track with a BPM records which source supplied it and at what confidence; the ladder is inspectable and disagreements are retained |

## Quality

| ID | Requirement | Phase | Acceptance |
|---|---|---|---|
| REQ-26 | Parsing and normalization logic is unit-tested against a real-oddity fixture corpus | 3, 5 | Coverage on `domain/` and `sources/*/parse.py` is meaningful, not nominal |
| REQ-27 | No test touches the network | 1 | HTTP mocked via `respx` / recorded fixtures; CI runs with networking off |
| REQ-28 | Marts declare a coverage note and first-reliable date | 6 | The collection ramp cannot be mistaken for a trend |
| REQ-29 | Lint, format and type checks run identically locally and in CI | 1 | `make lint` and CI invoke the same commands |
