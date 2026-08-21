# Phase 2: Ingestion Framework - Context

**Gathered:** 2026-08-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A reusable, polite, replayable ingestion substrate, so every later connector is
a thin adapter rather than its own snowflake.

**In scope:** bronze schema, the shared HTTP layer (rate limiting, robots.txt,
retry, caching), the job contract and run tracking, `emeye status`, the
reparse path, and the scheduler container.

**Out of scope:** any actual collector. Phase 2 ships the substrate and proves
it against a fixture, not against Beatport. The first real source is Phase 3.
Silver tables are also out — bronze plus the machinery that fills it, nothing
downstream of it.

</domain>

<decisions>
## Implementation Decisions

### Bronze storage
- **D-01:** Payloads stored as **JSONB** (owner, 2026-08-21). Queryable directly
  in psql, so "why did this parser get it wrong" is answerable without a
  round-trip through Python, and Postgres TOAST-compresses it automatically.
  At this project's volume the space argument for opaque `bytea` does not apply.
- **D-02:** Non-JSON payloads (Beatport ships HTML with embedded JSON) are
  wrapped: the extracted JSON goes in the JSONB column, and the surrounding
  markup is preserved in a text column on the same row. Bronze must stay
  replayable even when the *extraction* was wrong, not just the parse.
- **D-03:** `raw_document` is **append-only**. No UPDATE, no DELETE, enforced by
  a table-level trigger rather than convention — the invariant is too important
  to leave to reviewer discipline.
- **D-04:** Natural key is `(source, endpoint, params_hash, fetched_at)`.
  `content_hash` (sha256 of the payload) is stored but is **not** the key: the
  same content fetched on two days is two facts, and collapsing them would
  destroy the chart time series.
- **D-05:** Retention is indefinite (owner). No TTL, no pruning job.

### HTTP layer
- **D-06:** **Synchronous** `httpx`. At ~2 chart requests plus a handful of
  detail fetches per day, async buys nothing and costs real complexity in
  testing and error handling.
- **D-07:** Rate limiting, robots.txt, retry/backoff and `Retry-After` live in
  the shared client and are **not** overridable per source (REQ-18). A source
  adapter cannot opt out of politeness.
- **D-08:** **robots.txt is a first-class component**, not a flag: fetched per
  host, cached with a TTL, consulted on every request, and **failing closed**
  when it cannot be read. A source that will not serve robots.txt does not get
  crawled.
- **D-09:** `Retry-After` is obeyed absolutely, including values longer than the
  configured timeout. A 429 is the upstream telling us we got it wrong.
- **D-10:** Backoff is exponential with jitter, capped, with a maximum attempt
  count from settings. `tenacity` owns this.
- **D-11:** The User-Agent comes from settings and is required (already enforced
  in Phase 1). No browser impersonation, ever.
- **D-12:** A cache hit is always preferred over a request. The client checks
  bronze before fetching and records `skipped_cache` when it declines to.

### Job contract and run tracking
- **D-13:** Every job is a class implementing a small contract: `source`,
  `job_name`, and a `run()` that returns a result object. The runner — not the
  job — owns `ingest_run` bookkeeping, so a job cannot forget to record itself.
- **D-14:** `ingest_run` statuses: `started`, `succeeded`, `failed`,
  `skipped_cache`. `skipped_cache` is load-bearing: it is how the "one fetch per
  chart per reset" invariant is *proved* rather than assumed.
- **D-15:** A run row is written **before** work begins and updated on
  completion, so a crashed process leaves a `started` row rather than no
  evidence. `emeye status` reports stale `started` rows as suspicious.
- **D-16:** Failures record the exception text and traceback, then re-raise or
  skip deliberately. No silent `except Exception: pass` (CLAUDE.md).
- **D-17:** Idempotency is the job's responsibility and the test suite's
  concern: running any job twice must change no row counts (REQ-17).

### Reparse
- **D-18:** `emeye ingest reparse <source>` rebuilds from bronze alone, with
  networking unavailable — proven by a test that runs it under the network
  guard (REQ-02). This is the phase's most important single guarantee: it is
  what makes a wrong parser a cheap mistake instead of lost data.

### Scheduler
- **D-19:** cron in a container invoking `emeye` commands (owner-confirmed).
  Same image as the app, different command. No Dagster.
- **D-20:** The scheduler is **opt-in via a compose profile**, so `make up` on a
  workstation does not silently start collecting. Deployment enables it
  deliberately.

### Claude's Discretion
- Exact table/column naming within the `raw_document` / `ingest_run` shape.
- Whether the append-only trigger is a rule or a trigger function.
- Structure of the job registry and how the CLI discovers jobs.
- `emeye status` output formatting (Rich table assumed).

</decisions>

<specifics>
## Specific Ideas

- Phase 2 must be provable **without touching a live upstream**. Every test
  runs under the network guard from Phase 1, using `respx` fixtures. The
  substrate is validated against a fake source; Beatport is Phase 3's problem.
- The politeness machinery is the part that would be embarrassing to get wrong.
  It should be difficult to bypass by accident and impossible to bypass by
  configuration.

</specifics>

<canonical_refs>
## Canonical References

- `CLAUDE.md` — legal/ethical posture (binding), code conventions, invariants
- `docs/DATA-SOURCES.md` — per-source rate limits, the Beatport cadence design
- `docs/ARCHITECTURE.md` — bronze contract, layer boundaries
- `.planning/REQUIREMENTS.md` — REQ-02, REQ-17, REQ-18, REQ-19, REQ-21, REQ-23
- `.planning/phases/01-foundation/01-0{1,2,3,4}-SUMMARY.md` — the seams this builds on

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `emeye.config.get_settings()` — already carries `user_agent`,
  `default_rate_limit_per_sec`, `http_timeout_seconds`, `max_retries` and the
  per-source `enable_*` flags. REQ-23's opt-in gating is already half-built.
- `emeye.db.engine.session_scope()` — transactional scope with rollback.
- `emeye.db.base.Base` + Alembic autogenerate, with a test that fails on drift.
- `emeye.logging.get_logger()` — structured logging; every ingest must log
  source, endpoint, item count, cache hit/miss and duration.
- `tests/conftest.py` network guard — Phase 2's tests inherit it for free, and
  the reparse-offline proof depends on it.

### Established Patterns
- CLI groups are registered in `cli/groups.py`; `ingest` and `status` currently
  hold stubs that exit 2. Phase 2 replaces those two.
- Every schema change is an Alembic revision with a working downgrade.

### Integration Points
- `raw_document` is what Phase 3's collectors write and Phase 5's parsers read.
- The job contract is what Phase 3, 4 and 6 jobs implement.
- `ingest_run` is what `emeye status` reads, and in Phase 8 also carries
  backup age.

</code_context>

<deferred>
## Deferred Ideas

- Bronze payload compression/pruning — retention is indefinite by decision.
- Parallel or async fetching — revisit only if a source genuinely needs it,
  which per the collection posture it should not.
- A dead-letter queue for repeatedly failing documents — `ingest_run` history
  is sufficient at this scale.
- Prometheus/metrics export — `emeye status` is the interface.

</deferred>
