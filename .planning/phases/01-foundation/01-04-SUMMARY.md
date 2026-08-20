# Plan 01-04 — Licensing & Governance — Summary

**Completed:** 2026-08-20
**Status:** ✅ Done

## Decision

**AGPL-3.0-or-later**, chosen by the owner. Reasoning: AGPL's obligations are
well-understood and unambiguous, which reduces downstream licensing friction
compared with a bespoke source-available license. Supported by the fact that
emeye is network-deployable via the Phase 8 Streamlit UI, where a plain GPL
would leave the hosted-service loophole open.

## What was built

| Artifact | Content |
|---|---|
| `LICENSE` | Verbatim GNU AGPL v3.0 — 661 lines, checksum-verified against source |
| `pyproject.toml` | `license = { text = "AGPL-3.0-or-later" }` + OSI classifier |
| `README.md` | License section, separated from the data-collection posture section |
| `src/**/*.py` | SPDX header on every file |
| `emeye --version` | Prints copyright + no-warranty notice |
| `docs/LICENSING.md` | Decision, obligations, allowlist, remediation path |
| `docs/licenses/THIRD-PARTY.md` | Generated inventory, 43 distributions |
| `scripts/check_licenses.py` | Enforcement — allowlist, denylist, justified exceptions |

## Verification

- `LICENSE` md5 matches the fetched source byte-for-byte; §13 (Remote Network
  Interaction), the version line and the application appendix all present
- All four license surfaces agree on `AGPL-3.0-or-later`
- `scripts/check_licenses.py` → **OK, 43 distributions, no UNRESOLVED**
- SPDX header coverage across `src/` and `scripts/`: complete

## Findings

- **`psycopg` and `psycopg-binary` are LGPL-3.0-only** — confirmed, as
  anticipated at plan time. Compatible with AGPL-3.0 (LGPLv3 permits conveying
  under GPLv3 terms; GPLv3 and AGPLv3 works combine). The only non-permissive
  runtime dependency. Documented in `docs/LICENSING.md`.
- Dependency license spread: 25 MIT, 6 BSD-3-Clause, 4 Apache-2.0, 2 MPL-2.0,
  2 LGPL-3.0, 1 each ISC / BSD-2-Clause / PSF-2.0. No surprises.
- Package license metadata is genuinely inconsistent across the ecosystem
  (`License-Expression`, `License ::` classifiers, and free-text `License` all
  in use). The checker reads all three in reliability order rather than trusting
  one field.
- **The Essentia argument for AGPL no longer applies** — local audio analysis
  went out of scope when the owner confirmed there is no personal library. The
  network-deployment argument stands alone and the decision is unchanged, but
  `docs/LICENSING.md` records which reasons survive rather than leaving a stale
  justification in place.

## Deviations from plan

- Plan Task 4 called for `check_licenses.py` to be wired into CI. That wiring
  belongs to `01-03` and is deferred there as planned; the script itself is
  complete and passing.
- The `EXCEPTIONS` map is currently near-empty because no dependency needed one.
  The mechanism and its justification requirement are in place for when one does.
