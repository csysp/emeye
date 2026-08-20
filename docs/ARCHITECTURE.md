# Architecture

Local-first, single-user, batch. Everything runs in Docker Compose on the
owner's machine. No cloud, no queues, no services that outlive `make down`.

---

## Container topology

| Service | Image | Role |
|---|---|---|
| `postgres` | `postgres:16` | Warehouse. Named volume, the only stateful thing. |
| `app` | local build | CLI + libraries. Where ingest, dbt and analysis run. |
| `scheduler` | same image as `app` | cron-style loop invoking `emeye` commands. |
| `streamlit` | same image as `app` | Exploration UI on `localhost:8501`. |
| `metabase` *(optional)* | `metabase/metabase` | Point-and-click SQL browsing. |
| `jupyter` *(optional)* | same image as `app` | Notebooks against the warehouse. |

One image for all Python services; the command differs. `.env` supplies
credentials and feature flags; `.env.example` documents every variable.

Portability rule: the only host requirement is Docker. Everything is bind-mount
+ named volume; the machine can be Linux, macOS or Windows/WSL2 without change.

---

## Data flow

```
   ┌──────────┐   fetch     ┌───────────┐   parse     ┌──────────┐   dbt      ┌────────┐
   │ upstream │ ──────────► │  BRONZE   │ ──────────► │  SILVER  │ ─────────► │  GOLD  │
   └──────────┘  polite,    └───────────┘  replayable └──────────┘  tested    └────────┘
                 cached      raw payloads   normalized  entities    marts        │
                                                                                 ▼
                                                        Streamlit · Parquet · DuckDB · notebooks
```

### Bronze — raw landing zone

```sql
raw_document (
  id            bigserial primary key,
  source        text        not null,   -- 'beatport' | 'musicbrainz' | ...
  endpoint      text        not null,
  request_params jsonb      not null,
  fetched_at    timestamptz not null,
  http_status   int         not null,
  content_type  text,
  content_hash  text        not null,   -- sha256 of payload
  payload       jsonb,                  -- or bytea for HTML/compressed
  ingest_run_id bigint      references ingest_run(id)
)
```

- Append-only. Never updated, never deleted by application code.
- `unique (source, endpoint, request_params, content_hash)` — re-fetching an
  unchanged document is a no-op, which makes reruns free.
- Parsers read bronze, never the network. A parser bug is fixed by editing the
  parser and reparsing, not by re-scraping.
- Every fetch is attributed to an `ingest_run` row carrying status, counts,
  duration, and error text.

### Silver — normalized entities

Core tables:

| Table | Grain |
|---|---|
| `dim_artist` | one row per artist alias |
| `dim_label` | one row per label (with parent_label_id) |
| `dim_genre_source` / `dim_genre_canonical` / `bridge_genre_crosswalk` | SCD2 vendor genre + stable internal taxonomy |
| `dim_release` | one row per release (catalog grouping) |
| `dim_track` | one row per resolved track |
| `bridge_track_artist` | (track, artist, role) |
| `fct_chart_position` | (chart_id, chart_date, position, track_id) — daily |
| `fct_track_metric` | (track_id, source, metric, observed_at, value) — playcounts etc. |
| `xref_external_id` | (entity_type, entity_id, source, external_id, confidence, method) |
| `ingest_run` | one row per collector execution |

Rules:

- Every silver row carries `source`, `first_seen_at`, `last_seen_at`, and the
  bronze `content_hash` it derives from.
- Natural keys + `ON CONFLICT DO UPDATE` — ingestion is idempotent by construction.
- **No derived analytics columns.** Camelot code, title tokens, BPM buckets and
  normalized names are computed downstream so redefining them is a rebuild, not
  a migration.
- Entity resolution links live only in `xref_external_id`, so a bad matching
  heuristic can be re-run without touching entity tables.

### Gold — marts

dbt models, materialized as tables, tested (`not_null`, `unique`, accepted
values, relationship tests, plus custom "denominator present" tests).

| Mart | Grain | Answers |
|---|---|---|
| `mart_tempo_by_genre_month` | genre × month | BPM median/IQR/modes, release count |
| `mart_key_distribution_month` | genre × month × key | key share, minor share |
| `mart_title_token_month` | genre × month × token | token share of releases |
| `mart_label_share_month` | genre × month × label | release share, chart share, HHI |
| `mart_artist_activity_month` | genre × month × artist | output, newcomer/attrition flags |
| `mart_remix_network_year` | artist pair × year | remix edges for graph analysis |
| `mart_chart_dynamics_daily` | chart × date × track | entries, peaks, longevity |
| `mart_forecast_run` / `mart_forecast_point` | run / (run, horizon) | forecasts + intervals |

Every mart carries `population` (`catalog` | `chart`), `n` (denominator), and a
`coverage_note` describing the first date the series is trustworthy.

---

## Layer contracts

| From → To | Contract |
|---|---|
| network → bronze | May fail; retries and rate limits live here; nothing is interpreted |
| bronze → silver | Pure function of bronze. Deterministic, replayable, idempotent |
| silver → gold | SQL only (dbt). No Python, no network, no hidden state |
| gold → consumers | Read-only. Consumers never write to the warehouse |

If a step needs to break its contract, that is a design discussion, not a
workaround.

---

## Scheduling

`scheduler` runs a small cron table invoking CLI commands:

| Cadence | Command | Why |
|---|---|---|
| daily, off-peak | `emeye ingest charts` | **Irrecoverable if missed** |
| daily | `emeye ingest new-releases` | Catches releases before metadata churn |
| weekly | `emeye enrich musicbrainz` / `deezer` | Fill BPM/ISRC/MBID gaps |
| weekly | `emeye ingest metrics lastfm` | Playcount deltas need regular snapshots |
| monthly | `emeye ingest dump discogs` | Bulk refresh from data dumps |
| after any ingest | `emeye dbt build` | Marts stay current |
| weekly | `emeye forecast run` | Forecasts are versioned data, not ad-hoc output |

Jobs are individually re-runnable and idempotent. A missed day is re-runnable
for catalog data and permanently lost for charts — hence the daily chart job's
priority and its own alerting.

---

## Analysis surfaces

- **Streamlit** (`app/`) — the default surface. Saved views over the marts:
  tempo drift, key mix, title tokens, label concentration, forecast vs. actual.
- **Parquet exports** (`emeye export`) — marts written to `exports/` for
  **DuckDB** ad-hoc analysis and notebook work without touching Postgres.
- **Notebooks** (`notebooks/`) — exploratory only. A finding that matters
  graduates into a dbt model or an `analytics/` function; notebooks are never
  a dependency of anything.
- **Metabase** (optional) — for clicking around the warehouse without writing
  a Streamlit page.

---

## Forecasting subsystem

```
mart_* (history) → feature builder → backtest harness → model registry → mart_forecast_*
                                            │
                                            └── evaluation vs. actuals (rolling)
```

- Backtesting is **rolling-origin with expanding windows**. Random splits leak.
- Baselines (seasonal naive, drift) are computed for every target, every run,
  and stored alongside the model's forecast. A model that does not beat the
  baseline on MASE does not ship.
- A forecast run persists: model id, params, training window, feature set, git
  commit, and the forecast points with prediction intervals. Accuracy is scored
  later against what actually happened, so the system grades its own history.

---

## Operational concerns

- **Backups.** The Postgres volume is the only irreplaceable asset (bronze
  cannot be re-fetched for chart history). `emeye backup` produces a compressed
  dump to a configured path; the owner chooses the destination.
- **Storage growth.** Bronze payloads dominate. Compress payloads, and decide a
  retention policy (keep-forever vs. prune parsed HTML after N months) as an
  explicit configuration, not a silent default.
- **Observability.** `ingest_run` is the log of record: counts, durations, cache
  hit rate, error text. `emeye status` renders it. That is the whole monitoring
  story, deliberately.
- **Failure posture.** Ingest failures are recorded and surfaced; they never
  corrupt silver, because silver only ever derives from complete bronze rows.
