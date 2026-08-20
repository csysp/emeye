# Data Sources

Per-source reference: how we reach it, what it gives us, what it costs, and what
the rules are. **Update this file the moment you discover an upstream quirk** —
undocumented pagination caps, inconsistent key formats, silent truncation. That
knowledge is expensive to rediscover.

Status legend: 🟢 planned core · 🟡 optional / later · 🔴 out of scope for now

---

## 🟢 Beatport — primary catalog + charts

**Why:** the single best source of club-music release metadata. It is the only
source that reliably carries BPM **and** musical key **and** a genre taxonomy
built for DJs, on essentially the whole commercial release landscape.

**Primary origin, cross-referenced rather than sole-sourced.** Most tempo and
key values enter the warehouse from Beatport. They are vendor-supplied, and they
are cross-checked against Deezer, MusicBrainz and Discogs rather than taken
alone — not because vendor data is expected to be wrong (false-read rates are
low, and these catalogs are the sources of truth for their own data) but because
coverage is patchy and a second reading is cheap. Where sources disagree, keep
both and pick by ladder rank; see the BPM resolution ladder below.

**Access reality**

- Beatport operates a `v4` REST API (`api.beatport.com/v4/`) that is
  **partner-gated** — there is no open self-serve developer signup.
  **Decision (owner, 2026-08-20): sanctioned/partner access is not pursued.**
  At chart-only volume the API would buy nothing that a handful of daily page
  fetches does not, and the application overhead is not worth it.
- Absent credentials, the practical route is the public website's own embedded
  data payloads (the Next.js app ships structured JSON alongside each page).
  This is still scraping. Treat it as such.
- Assume everything here is subject to change without notice. Parsers must fail
  loudly (record the bronze document, raise) rather than silently produce nulls.

**Fields we care about**

| Field | Notes |
|---|---|
| `track_id`, `slug` | Beatport's own identifier — our `xref_external_id` anchor |
| `name`, `mix_name` | Title and mix descriptor — **decompose, don't concatenate** |
| `artists[]`, `remixers[]` | Roles matter; a remixer is not a primary artist |
| `bpm` | Integer as reported; see half/double-time caveat in DOMAIN.md |
| `key` | e.g. `A min`, `F♯ maj` — normalize to `(tonic_pc, mode)` |
| `genre`, `sub_genre` | Versioned taxonomy — see genre drift in DOMAIN.md |
| `label` (+ id) | Label dimension anchor |
| `release` (+ id, catalog number) | Release grouping |
| `publish_date` / `new_release_date` | Two different dates; capture both |
| `isrc` | Cross-service join hint |
| `length_ms` | Needed for the "extended mix length inflation" question |
| `exclusive`, `preorder` | Explains chart timing anomalies |
| chart position, chart date, chart genre | Time-series fact, daily grain |

**Chart surfaces in scope (v1)**

Scope is deliberately narrow — a narrow unbroken series is worth more than broad
shallow coverage, and it keeps request volume near zero:

- **Top 100 overall** — the headline sales chart
- **Hype 100** — the paid-promotion-free surface, a different bias profile

Explicitly **not** in v1 scope: per-genre Top 100s, new-release ordering,
Beatport DJ charts. Each is a separate ongoing request stream, and none is
needed for the v1 questions. They can be added later — but note that adding them
later means their history starts later.

**Collection cadence — minimal by design**

The job runs **on chart reset, once per chart**, not on a fixed polling loop:

1. Establish the reset cadence empirically in plan `03-01` (observed content
   change, plus any `Last-Modified`/`ETag` the origin offers). Do not assume;
   measure, then record the finding here.
2. Fetch each in-scope chart exactly **once per reset window**. A re-run inside
   the same window must serve from bronze and issue **zero** requests.
3. Fetch track detail **only for track IDs not already in the warehouse**. Chart
   turnover is modest, so this cost falls steadily as the catalogue fills — the
   steady state is a few detail fetches per day, not a hundred.

Steady-state volume is on the order of **2 chart requests plus a handful of
detail requests per day**. If a design implies materially more than that, the
design is wrong.

**Rules**

- ≤1 req/s, jittered, off-peak, `Retry-After` respected absolutely.
- Honor `robots.txt` on every run, every host.
- Cache in bronze; never re-fetch a document we already hold unchanged.
- Behind an explicit opt-in config flag. Terms of Service on beatport.com
  prohibit automated collection; the owner is the one who decides to enable it,
  and the tool must make that a conscious choice, not a default.
- Historical charts are **not** retrievable. Backfill attempts should be limited
  to the Internet Archive (best-effort, sparse) and clearly flagged as such.

---

## 🟢 MusicBrainz — entity backbone

**Why:** open, canonical, and the only source with proper **relationship**
modelling — "X remixed Y", "A is an alias of B", "recording ↔ ISRC".

- **API:** `https://musicbrainz.org/ws/2/` — JSON, no key required.
- **Hard rule: 1 request/second**, and a descriptive `User-Agent` with a contact
  address is mandatory. Violations get IP-banned.
- **Bulk:** full database dumps published twice weekly. For any backfill of more
  than a few thousand entities, use the dump, not the API.
- **Gives us:** MBIDs for artist/release/recording, aliases and legal names,
  ISRC ↔ recording mapping, remixer/producer relationships, area (country) for
  scene-geography analysis, artist begin/end dates.
- **Caveats:** electronic single/EP coverage is thinner than for album-oriented
  genres; BPM and key are largely absent; white-label and promo-only releases
  are under-represented.

---

## 🟢 Discogs — labels, credits, depth

- **API:** `https://api.discogs.com/` — free personal-access token; 60
  requests/minute authenticated, 25 unauthenticated. `User-Agent` required.
- **Bulk:** monthly XML data dumps (artists, labels, releases, masters) on S3.
  **Use the dumps for bulk work** — the API is far too slow for catalog-scale.
- **Gives us:** label hierarchies (sublabels, parent companies), catalog numbers,
  Discogs "styles" (an independent genre opinion — useful as a cross-check on
  Beatport's taxonomy), detailed credits (remix, engineering, mastering),
  format/vinyl history, community have/want counts as a demand proxy.
- **Caveats:** user-submitted, so quality varies; styles are folksonomic; BPM/key
  effectively absent.

---

## 🟢 Deezer — free BPM cross-check

- **API:** `https://api.deezer.com/` — most read endpoints need no auth.
- **Gives us:** `bpm` and `gain` on the track object, `isrc`, duration,
  release date, artist/album links, `rank` as a rough popularity signal.
- **Why it matters:** the only free, unauthenticated **tempo** source. Use it to
  audit Beatport BPM values and to fill gaps for tracks Beatport lacks.
- **Caveats:** BPM is algorithmically derived and sometimes 0/absent or
  half/double-time; no key field; rate limit is undocumented — self-limit to
  ~1–5 req/s and back off hard on `429`.

---

## 🟢 Last.fm — popularity over time

- **API:** `https://ws.audioscrobbler.com/2.0/` — free API key.
- **Gives us:** listeners, playcount, user-applied tags (a genre opinion built
  by listeners rather than by a store), similar-artist graph, chart endpoints.
- **Caveats:** tags are noisy and gameable; playcounts are cumulative snapshots,
  so **capture them on a schedule** to derive deltas — historical playcount
  curves are not retrievable after the fact.

## 🟢 ListenBrainz — open listening data

- **API:** `https://api.listenbrainz.org/` — open; token only for submission.
- **Gives us:** actual listen counts keyed by MBID, sitewide and per-artist
  statistics, and full data dumps for offline analysis.
- **Why:** an unencumbered, dump-friendly alternative to Last.fm that joins
  cleanly to the MusicBrainz backbone.

---

## 🟢 Spotify — metadata + streaming-side charts (never tempo)

**Role (owner, 2026-08-20):** an official-API source for **playlist/chart
membership and track metadata**. It is a second, independent chart *population*:
Beatport charts what the DJ-purchase market buys, Spotify charts what the
streaming audience plays. Both are worth snapshotting; they must never be
blended into one series without labelling.

⚠️ **Do not design tempo or key analytics around Spotify.** The
`/audio-features` and `/audio-analysis` endpoints — the source of the
tempo/key/energy/danceability numbers everyone used to build on — were
**deprecated for new applications in November 2024**. Assume they are
unavailable to this project. BPM comes from Beatport and Deezer; see the BPM
resolution ladder below.

**Access:** OAuth **client-credentials** flow (no user login needed for public
catalog and public playlist reads). Requires registering a developer app.

**Useful fields**

| Field | Notes |
|---|---|
| `id`, `uri` | Spotify identifier — `xref_external_id` anchor |
| `external_ids.isrc` | The best cross-service join hint we get from Spotify |
| `name`, `artists[]`, `album` | Metadata cross-check; mix names appear in `name` |
| `duration_ms` | Independent length check |
| `popularity` (track + artist) | Mainstream-reach proxy over time — snapshot it, it mutates |
| `album.release_date` (+ precision) | Note the precision field; it is often year-only |
| playlist membership + position | The chart fact, dated grain |

**Playlists to track**

**v1 tracks `mint` and nothing else** (owner, 2026-08-20). Additional playlist
pipes are additive and can be built later — the only cost of deferring them is
that their history starts later.

Consequence worth stating plainly: with a single playlist, the Spotify chart
signal is all-or-nothing. If editorial access is unavailable, there is no
degraded Spotify chart signal — there is none at all.

⚠️ **Verify before building on this.** The same November 2024 change that
removed audio-features also **restricted access to Spotify-owned editorial
playlists** (Featured Playlists, category playlists, and the playlist endpoints
for Spotify-owned editorial content) for newly-registered applications. `mint`
is a Spotify-owned editorial playlist and may therefore be unreachable by a new
app. **This must be confirmed against a real app registration in plan `04-04`
before any playlist-tracking design is committed** — the answer determines
whether this source works as described.

Fallbacks if editorial playlists are confirmed unavailable:
- Track user-owned or third-party public playlists that mirror the same territory
- Use the separate Spotify Charts product (regional/genre top-streamed lists) if
  its terms permit personal collection — verify independently
- Accept Beatport as the sole chart signal and use Spotify for metadata only

Record whichever answer is found here, in this file, immediately. That finding
is expensive to rediscover.

**Rules**

- Never read, store, or derive from a Spotify tempo/key field, even if an
  endpoint appears to still serve one. A CI grep enforces this (REQ-32).
- Popularity and playlist membership are **mutable** — snapshot them as dated
  facts, never update in place.
- Respect the documented rate limits and back off on `429`.

## 🟡 Traxsource / Juno Download

Independent store catalogs with genre coverage Beatport under-serves —
Traxsource skews soulful/deep house and is a useful corrective to Beatport's
peak-time bias; Juno carries a broader vinyl and back-catalog range. HTML only,
no public API. Same scraping rules apply. Worth adding once the Beatport
pipeline is stable and we want to test whether observed trends are
Beatport-specific bias or real.

## 🟡 Resident Advisor

Events, festival lineups, and club bookings — the demand side of the industry
(who is actually being booked, where, and how often). No sanctioned public API.
Interesting for correlating chart success with touring activity; strictly a
later-phase idea.

## 🟡 Local audio analysis (Essentia / librosa)

If the owner has an audio library, local analysis is the **only** way to get
ground truth for BPM and key and thereby measure how wrong vendor metadata is.
Runs entirely offline on owned files. No legal exposure. Valuable as a
validation set even at a few hundred tracks.

## 🔴 1001Tracklists

The best available record of what DJs actually play — and therefore the most
tempting source here. No API, explicit anti-automation terms, and aggressive
bot protection. **Out of scope.** Do not build a collector. Revisit only if a
sanctioned data path appears.

## 🔴 Bandcamp / SoundCloud

Bandcamp has no public API (the sales feed is undocumented and unstable);
SoundCloud's API registration has been effectively closed for years. Both are
relevant to underground release trends but neither offers a dependable,
sanctioned route today.

---

## BPM resolution ladder (REQ-33)

Not every track arrives with a usable tempo — Spotify-charting tracks in
particular may have no BPM anywhere in our data. BPM is resolved through an
**ordered ladder**, and the winning source is recorded on the row alongside the
value. Every source that had an opinion is retained, so disagreement stays
visible.

| Rank | Source | Notes |
|---|---|---|
| 1 | **Beatport** | Primary origin. Vendor-reported, algorithmic, DJ-oriented |
| 2 | **Deezer** | Free, unauthenticated `bpm` on the track object — the main independent check |
| 3 | **AcousticBrainz dump** | Collection stopped in 2022, but the historical dump is still downloadable and MBID-keyed. Static lookup, zero request cost. Verify current availability before relying on it |
| 4 | **MusicBrainz / Discogs** | Sparse for tempo; useful mainly via linked data |
| ~~5~~ | ~~Local audio analysis (Essentia/librosa)~~ | **Out of scope (owner, 2026-08-20).** emeye aggregates what the industry publishes — the vendor tag is the object of study, not a noisy measurement of it. Re-deriving tempo from audio would answer a different question |

Rules:

- Record `bpm_source` on every resolved value. This is **provenance and coverage
  accounting** — which source filled which gap, and how much of a series rests
  on the fallback tiers — not a quality audit of the vendors.
- **Never average across sources.** BPM is ambiguous by a factor of two: 87 and
  174 are both correct readings of the same drum & bass track, and their mean of
  130.5 describes nothing. This is a hazard in the *representation*, entirely
  independent of how accurate the sources are, so it holds no matter how much
  the upstream data is trusted. Pick a winner by ladder rank, fold to the
  canonical band, keep the alternatives.
- Expect **low disagreement rates**. Where sources do differ beyond the
  half/double-time relationship it is worth a look, but this is housekeeping —
  the project does not treat vendor data as suspect by default.

---

## Cross-source join strategy

Resolution order, best key first:

1. **ISRC** — strongest cross-service key. Missing often, occasionally reused
   incorrectly across a remix and its original. A strong hint, never a PK.
2. **MusicBrainz MBID** — canonical once resolved; resolve via ISRC, then via
   fuzzy (artist, title, duration) matching with a manual review queue.
3. **Fuzzy composite** — normalized title + normalized artist set + duration
   within ±3s. Store the match score and the method; never overwrite a
   higher-confidence link with a lower-confidence one.

Every external identifier lands in a single `xref_external_id` table
(`entity_type`, `entity_id`, `source`, `external_id`, `confidence`, `method`,
`linked_at`) so that a bad matching heuristic can be re-run without touching the
entity tables.

---

## Rate-limit summary

| Source | Self-imposed limit | Auth | Bulk dumps |
|---|---|---|---|
| Beatport | ≤1 req/s, jittered, off-peak | none / partner | ❌ |
| MusicBrainz | 1 req/s (enforced) | none, UA required | ✅ twice weekly |
| Discogs | 60/min (enforced) | token | ✅ monthly |
| Deezer | ≤5 req/s self-imposed | none | ❌ |
| Last.fm | ~5 req/s self-imposed | API key | ❌ |
| ListenBrainz | ~1 req/s | none for reads | ✅ |
| Spotify | per OAuth quota | OAuth | ❌ |
