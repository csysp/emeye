# Domain Reference

Electronic / club music specifics that the data model and analytics depend on.
These are not preferences — getting them wrong silently corrupts every long-run
series we produce.

---

## 1. Musical key

### Storage

Store keys as a canonical pair, never as a display string:

- `tonic_pc` — pitch class, integer `0..11`, where `0 = C`, `1 = C♯/D♭`, … `11 = B`
- `mode` — enum `major` | `minor`

Everything else (Beatport's `A min`, Camelot `8A`, Open Key `1m`, MusicBrainz's
`A minor`) is a **render** of that pair, computed on read.

### Why

- **Enharmonic equivalence.** `D♯ min` and `E♭ min` are the same key written two
  ways; sources disagree about which spelling to use, sometimes within one
  catalog. Storing the string produces two phantom keys and halves the counts
  for both.
- **Camelot is derived, not primary.** Camelot/Open Key are DJ-facing
  relabelings of the circle of fifths. Deriving them means we can change the
  rendering without a migration.

### Camelot mapping

Camelot numbers walk the circle of fifths; `A` = minor, `B` = major. Relative
major/minor pairs share a number (e.g. `8A` = A minor, `8B` = C major).

| Camelot | Key | | Camelot | Key |
|---|---|---|---|---|
| 1A | A♭ minor | | 1B | B major |
| 2A | E♭ minor | | 2B | F♯ major |
| 3A | B♭ minor | | 3B | D♭ major |
| 4A | F minor | | 4B | A♭ major |
| 5A | C minor | | 5B | E♭ major |
| 6A | G minor | | 6B | B♭ major |
| 7A | D minor | | 7B | F major |
| 8A | A minor | | 8B | C major |
| 9A | E minor | | 9B | G major |
| 10A | B minor | | 10B | D major |
| 11A | F♯ minor | | 11B | A major |
| 12A | D♭ minor | | 12B | E major |

Implement as a single lookup table in `src/emeye/domain/keys.py` with
round-trip tests in both directions.

### Analysis notes

- Club music skews heavily **minor** — the interesting metric is the *shift* in
  minor share over time and its variation by genre, not the level.
- Key popularity is partly an artifact of **synth and sample-pack defaults** and
  of DJ software's harmonic-mixing suggestions. Report it; don't over-interpret it.
- Vendor key detection is **algorithmic and wrong a meaningful fraction of the
  time** (relative major/minor confusion is the classic error). Any claim about
  key trends needs a validation pass against locally analyzed audio before it
  is treated as fact.

---

## 2. Tempo (BPM)

### The half/double-time problem

Detected BPM is ambiguous by a factor of two, and different sources resolve it
differently for the same track. Genres with a wide-spread convention:

| Genre | Commonly reported as | Also seen as |
|---|---|---|
| Drum & Bass | 172–176 | 86–88 |
| Dubstep / Riddim | 140 | 70 |
| Footwork / Juke | 160 | 80 |
| Trap / Halftime | 140–150 | 70–75 |
| UK Garage | 130–138 | 65–69 |
| Amapiano | 112–115 | — (rarely folded) |

**Rule:** store `bpm_reported` exactly as the source gave it, plus a derived
`bpm_canonical` folded into the genre's expected band using a per-genre range
table. Never overwrite the reported value; the folding logic *will* be revised.

### Expected bands (starting point — refine from data)

| Genre bucket | Typical band |
|---|---|
| Deep House / Organic House | 110–122 |
| Amapiano / Afro House | 110–125 |
| House / Jackin | 120–128 |
| Tech House / Minimal-Deep Tech | 124–132 |
| Melodic House & Techno / Progressive | 118–126 |
| Indie Dance / Nu Disco | 110–124 |
| Techno (Peak Time / Driving) | 132–145 |
| Techno (Raw / Deep / Hypnotic) | 125–140 |
| Hard Techno / Hard Dance | 145–175 |
| Trance | 132–142 |
| Psy-Trance | 138–148 |
| Breaks / Electro | 125–140 |
| UK Garage / Bassline | 130–140 |
| Drum & Bass | 168–180 |
| Dubstep / Bass | 138–142 |

These bands are **hypotheses to be measured, not filters to be enforced.**
Never drop a row for falling outside its band — flag it.

### Analysis notes

- BPM distributions are **multi-modal**; a genre mean is close to meaningless.
  Report median, IQR, and modal peaks (kernel density or 1-BPM histogram).
- Integer clustering is severe — producers pick round numbers (128, 130, 140).
  Expect spikes, and don't mistake a spike for a distribution.
- The widely-discussed "techno keeps getting faster" narrative is exactly the
  kind of claim this project exists to test properly: per-genre, with the
  release-count denominator visible, and with the taxonomy-drift break dates
  marked on the chart.

---

## 3. Titles and mix names

### Decomposition

`"Nightdrive (Somebody's Extended Remix) feat. Guest"` decomposes into:

| Field | Value |
|---|---|
| `title` | `Nightdrive` |
| `mix_name` | `Somebody's Extended Remix` |
| `mix_kind` | `remix` |
| `remixers[]` | `Somebody` |
| `featured[]` | `Guest` |
| `is_extended` | `true` |

`mix_kind` enum: `original`, `extended`, `radio_edit`, `remix`, `rework`,
`rerub`, `vip`, `dub`, `edit`, `live`, `instrumental`, `acapella`, `bootleg`,
`mashup`, `tool`, `intro`, `continuous_mix`, `unknown`.

Parse **once**, in `src/emeye/domain/titles.py`. Every downstream consumer uses
the parsed fields. This parser is the highest-value unit-test target in the
codebase — build a fixture corpus of real oddities as you find them.

### Known parsing hazards

- Nested and multiple parens: `Track (Remix) (Extended Mix)`.
- Square brackets used interchangeably with parens.
- Dashes instead of parens: `Track - Extended Mix`.
- Remixer names containing `&`, `feat.`, `vs`, or their own parentheses.
- `Original Mix` is a Beatport convention that means "not a remix", not a mix
  name; treat it as `mix_kind = original` and drop it from title tokens.
- Non-Latin scripts, emoji, and typographic quotes/dashes — normalize Unicode
  (NFKC) and fold typographic characters before tokenizing.
- Label-added suffixes and catalog numbers leaking into the title field.

### Title trend analysis

- Tokenize on the **cleaned title only** (mix name and `feat.` removed),
  lowercase, Unicode-normalized, stopwords removed.
- Track unigram and bigram frequency per month, per genre. Report **share of
  releases containing the token**, not raw counts — raw counts track catalog
  growth, not language trends.
- Useful derived signals: mean title length, share of one-word titles, share of
  non-English titles, share with `feat.`, share of all-caps, emoji presence.
- **Extended-mix length inflation** is a distinct, testable question: median
  `length_ms` of `mix_kind = extended` over time, per genre.

---

## 4. Genre taxonomy and its drift

Beatport's genre list is a **commercial merchandising taxonomy**, not a stable
scientific one. It has been reorganized more than once — notably the split of
`Techno` into `Techno (Peak Time / Driving)` and `Techno (Raw / Deep /
Hypnotic)`, the promotion of `Afro House`, `Organic House / Downtempo`,
`Amapiano` and `Melodic House & Techno` to top-level genres, and repeated
renames of the trance and hard-dance buckets.

**Consequence:** any series keyed on the vendor's genre string breaks at each
rename date, and the break looks exactly like a real trend.

**Model it properly:**

- `dim_genre_source` — the vendor's genre as observed, with `source`,
  `source_genre_id`, `name`, `valid_from`, `valid_to` (a slowly-changing
  dimension, type 2).
- `dim_genre_canonical` — our own stable internal taxonomy, deliberately coarser
  than any vendor's.
- ⚠️ **Deferred, not built in v1** (charts-only scope — see PROJECT.md Key Decisions).
  `bridge_genre_crosswalk` — many-to-many mapping with `weight`, so a vendor
  split can be mapped back onto one canonical genre for continuity.
- Every long-run chart must be able to render on the canonical taxonomy, and
  every taxonomy change date must be available as an annotation layer.

Discogs "styles" and Last.fm tags are **independent genre opinions**. Keep them
as separate labels, not merged into the same field — disagreement between them
is itself a useful signal about genre boundary shift.

---

## 5. Artists, remixers, and credits

- **Roles are first-class.** `bridge_track_artist(track_id, artist_id, role)`
  with `role ∈ {primary, featured, remixer, producer, original_artist}`.
  Counting a remixer as a primary artist inflates output metrics badly.
- **Display strings are not identities.** Split on ` & `, `, `, ` x `, ` X `,
  ` vs `, ` vs. `, ` feat. `, ` ft. `, ` featuring `, ` presents `, ` pres. `,
  ` with `. Each of these is also legitimately part of some artists' names —
  maintain an exception list and never split a name that matches a known artist
  exactly.
- **Aliases are the norm** in this genre. One person may release under several
  names, and the alias graph is real information (MusicBrainz models it). Keep
  `dim_artist` at the alias level and add `dim_person` grouping later if needed.
- **Metrics worth building:** releases per artist per year, newcomer rate (first
  appearance in the dataset), attrition rate, remix-to-original ratio, the
  remixer↔artist bipartite graph and its communities, label-hopping rate.

---

## 6. Labels

- Labels have **parents and sublabels** (Discogs models this); "who dominates"
  is a different answer at label vs. label-group level. Compute both.
- **Concentration metrics:** top-N share of releases and of chart positions, and
  the Herfindahl–Hirschman Index per genre per period. This is the rigorous
  version of "the scene is consolidating".
- **Roster churn:** artists gained/lost per label per year; median artist tenure.
- Label names are reused and rebranded — key on the vendor's label id, not the
  name, and keep a name-history table.

---

## 7. Charts vs. catalog — the central bias

Two fundamentally different populations, never to be blended silently:

| | Catalog | Charts |
|---|---|---|
| Population | everything released | what sold / was promoted |
| Bias | store acceptance policy | marketing spend, playlist placement, DJ support |
| Best for | "what is being made" | "what is succeeding" |
| Backfillable | mostly yes (release dates) | **no** |

Every mart declares which population it draws from in its name and its
description. A "tempo trend" from charts and a "tempo trend" from catalog are
different findings and can legitimately point in opposite directions — that
divergence is one of the more interesting things this project can measure.

---

## 8. Seasonality and calendar effects

Deseasonalize before claiming a trend. Known annual structure:

- **March** — Miami Music Week / WMC; a release surge aimed at the US season.
- **May–September** — Ibiza season; peak-time and vocal-house weighting rises.
- **October** — Amsterdam Dance Event; the single biggest release spike of the
  year, and a deadline that shifts release dates by weeks.
- **December** — holiday slump plus "best of" compilations.
- **January** — reissue/remaster wave and label roster resets.
- **Weekly** — Beatport's release cadence clusters on Fridays; anything at daily
  grain has a strong day-of-week component.

---

## 9. Data quality hazards checklist

Confirm each of these is handled before trusting a series:

- [ ] Duplicate releases (re-release, remaster, compilation inclusion) deduped
- [ ] Half/double-time BPM folded, with the reported value preserved
- [ ] Enharmonic keys normalized
- [x] ~~Genre renames crosswalked to the canonical taxonomy~~ — deferred; v1 keeps the vendor string verbatim
- [ ] Chart vs. catalog population labelled
- [ ] Denominator (release count) reported alongside every rate
- [ ] Coverage ramp accounted for — our own collection start date is not a trend
- [ ] Exclusive/pre-order window handled when using release dates
- [ ] `mix_kind` filtered explicitly (are DJ tools and acapellas in or out?)
- [ ] Small-n periods suppressed or flagged
