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

**Access reality**

- Beatport operates a `v4` REST API (`api.beatport.com/v4/`) that is
  **partner-gated** — there is no open self-serve developer signup. If the owner
  can obtain sanctioned API credentials, that is the preferred path and this
  section should be rewritten around it.
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

**Chart surfaces worth snapshotting daily**

- Top 100 overall and Top 100 per genre
- "Hype" charts (paid-promotion-free surface — different bias profile)
- New-releases ordering per genre
- Beatport DJ charts (curated by artists — a distinct taste signal)

**Rules**

- Daily snapshot job, off-peak, ≤1 req/s, jittered, with `Retry-After` respected.
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

## 🟡 Spotify — metadata only, with a warning

⚠️ **Do not design tempo or key analytics around Spotify.** The
`/audio-features` and `/audio-analysis` endpoints (the source of the
tempo/key/energy/danceability numbers everyone used to build on) were
**deprecated for new applications in November 2024**. Assume they are
unavailable to this project.

What remains useful: release metadata, ISRC via the track object, artist
`popularity` and follower counts as a mainstream-reach proxy, playlist presence.
Requires OAuth client credentials.

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
