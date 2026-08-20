# emeye — Electronic Music Eye

A personal, local-first data warehouse and analysis toolkit for **electronic /
club music production trends**.

emeye ingests catalog and chart data from Beatport plus free open-music APIs
(MusicBrainz, Discogs, Deezer, Last.fm, ListenBrainz), normalizes it into a
PostgreSQL warehouse, and produces long-horizon trend analytics and forecasts
over tempo, key, song-title language, label dominance, and artist / remixer
activity.

Everything runs in Docker. Single user, no cloud, no accounts.

## Status

Pre-implementation. Planning artifacts live in [`.planning/`](.planning/);
architecture and conventions live in [`CLAUDE.md`](CLAUDE.md).

## Documentation

| Doc | What's in it |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Project direction, stack, architecture, conventions, guardrails |
| [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) | Per-source access, fields, rate limits, legal posture |
| [`docs/DOMAIN.md`](docs/DOMAIN.md) | Genre taxonomy, key/Camelot handling, title & mix-name grammar |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Data flow, layering, schema contracts |
| [`.planning/ROADMAP.md`](.planning/ROADMAP.md) | Phase breakdown |
| [`.planning/REQUIREMENTS.md`](.planning/REQUIREMENTS.md) | Numbered requirements |

## Method

Development follows [GSD Core](https://github.com/open-gsd/gsd-core), cloned
into `gsd-core/` and deliberately left untracked. Refresh with
`git -C gsd-core pull`.

## License

**AGPL-3.0-or-later.** See [`LICENSE`](LICENSE) for the full text and
[`docs/LICENSING.md`](docs/LICENSING.md) for the reasoning and the dependency
compatibility policy.

In plain terms: you may use, modify and share emeye freely, but if you
distribute it — **or run a modified version as a network service** — you must
offer your users the complete source of your version under these same terms.

## Legal posture on collected data

A separate concern from the license above: that one governs emeye's own code,
this one governs how emeye treats other people's data.

Personal research use only. Collectors honor `robots.txt`, rate-limit to a
trickle, identify themselves honestly, and never evade bot protection. No
third-party data is redistributed from this repository.
