# Licensing

## The decision

**emeye is licensed AGPL-3.0-or-later.** Decided by the owner on 2026-08-20 at
the `01-04` planning checkpoint.

`LICENSE` holds the complete, unmodified text of the GNU Affero General Public
License version 3. It is never summarized, reflowed, or edited — a modified
license text is a different license.

## Why

The owner's reasoning: AGPL's obligations are well-understood and unambiguous,
which *reduces* downstream licensing friction compared to a bespoke
source-available license whose terms every reader has to interpret for
themselves.

The supporting technical argument:

- **emeye is network-deployable.** Phase 8 adds a Streamlit UI. Under a plain
  GPL, someone could modify emeye, run it as a hosted service, and never publish
  their changes — distribution never occurs, so the copyleft never triggers.
  AGPL section 13 closes exactly that gap.
- **The dependency stack is entirely compatible.** MIT, BSD, Apache-2.0, ISC,
  MPL-2.0 and LGPL-3.0 all flow into an AGPL work.

One argument that applied at decision time no longer does: AGPL was also
attractive for keeping **Essentia** (AGPL-3.0) available for audio ground-truth
analysis. That work was subsequently taken out of scope — there is no personal
library to analyze. The network-deployment argument stands on its own, so the
decision is unchanged, but the record should be honest about which reasons
survive.

## What it obliges

Not legal advice — a plain-language orientation. The license text governs.

If someone distributes emeye or a modified version, **or runs a modified version
as a network service that users interact with**, they must offer those users the
complete corresponding source of their version, under these same terms. Copyright
and license notices must be preserved. Contributors grant patent rights.

For the owner's own local, personal use: nothing is required. The obligations
attach to conveying the software or offering it over a network to others.

## Where the license is stated

All four must agree. A disagreement between them creates real ambiguity about
which terms apply:

| Surface | Content |
|---|---|
| `LICENSE` | Verbatim GNU AGPL v3.0 text |
| `pyproject.toml` | `license = { text = "AGPL-3.0-or-later" }` + OSI classifier |
| `README.md` | Names the license, links `LICENSE` |
| `src/**/*.py` | `# SPDX-License-Identifier: AGPL-3.0-or-later` as line 1 |
| `emeye --version` | Prints the copyright and no-warranty notice |

## Dependency compatibility

Every runtime dependency must be license-compatible. This is enforced, not
remembered:

```bash
uv run python scripts/check_licenses.py            # check (CI runs this)
uv run python scripts/check_licenses.py --report   # regenerate the inventory
```

The generated inventory lives at `docs/licenses/THIRD-PARTY.md`.

### The allowlist

`ALLOWED` in `scripts/check_licenses.py` covers permissive licenses (MIT, BSD,
Apache-2.0, ISC, PSF, Zlib, Unlicense, HPND), weak copyleft (LGPL-3.0, MPL-2.0),
and the GPL family (GPL-3.0, AGPL-3.0). All of these permit inclusion in an
AGPL-3.0-or-later work.

`DENIED` names licenses that are actively incompatible or non-open-source:
GPL-2.0-only (cannot be combined with AGPL-3.0), SSPL-1.0, BUSL-1.1,
Commons Clause, Elastic-2.0.

### Notable current dependencies

- **`psycopg` / `psycopg-binary` — LGPL-3.0-only.** The one non-permissive
  runtime dependency. LGPL-3.0 is compatible with AGPL-3.0: LGPLv3 explicitly
  permits conveying under GPLv3 terms, and GPLv3 and AGPLv3 works may be
  combined. No action needed. Worth knowing it is there, because it would need
  a relinking review under any non-copyleft license.
- Everything else is MIT, BSD, Apache-2.0, ISC, MPL-2.0 or PSF.

### When the check fails

1. **`DENIED`** — do not add the dependency. Find an alternative. If there is
   genuinely none, the license decision itself has to be revisited, which is a
   conversation with the owner, not a code change.
2. **Not on the allowlist** — research the license. If it is genuinely
   compatible, add it to `ALLOWED` with a comment saying why. If not, treat it
   as `DENIED`.
3. **`UNRESOLVED`** — the package's metadata is missing or unparseable. Read the
   package's own `LICENSE` file, then add an entry to `EXCEPTIONS` with a
   justification string. **Never** add an exception without a reason; that is a
   silenced alarm, not an exception.

## Adding a dependency

Check it *before* it lands. An incompatible transitive dependency caught at
add-time is a five-minute problem; caught two years later it is a rewrite.

```bash
uv add <package>
uv run python scripts/check_licenses.py --report
git add docs/licenses/THIRD-PARTY.md
```

## New source files

Every `.py` file under `src/` starts with:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
```

CI checks this. It is one line and it is the thing that keeps the license
attached to code after it has been copied somewhere else.
